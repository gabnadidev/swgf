"""
Testes automatizados das regras de negócio e dos requisitos da B2.
Para rodar:  python manage.py test
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Cliente, Data, Mensagem, Mesa, Notificacao, RegraDeNegocioError, Senha, SessaoMesa, Ticket,
    Usuario,
)


def url(nome, *args):
    """Atalho para montar a URL de uma rota do app."""
    return reverse(f'swgfApp:{nome}', args=args)


class BaseTestCase(TestCase):
    """Cria o cenário comum: um administrador, dois atendentes e duas mesas."""

    def setUp(self):
        self.admin = Usuario.objects.create_user('chefe', password='x', is_adm=True)
        self.user = Usuario.objects.create_user('ana', password='x')
        self.outro = Usuario.objects.create_user('bia', password='x')
        self.mesa1 = Mesa.objects.create(numero=1)
        self.mesa2 = Mesa.objects.create(numero=2)


class RelacionamentoTests(BaseTestCase):
    """Requisito 1: relacionamentos 1:1 e 1:N."""

    def test_senha_e_ticket_sao_um_para_um(self):
        ticket = Ticket.emitir('João', 'normal')
        self.assertEqual(ticket.senha.ticket, ticket)  # acesso direto nos dois sentidos

    def test_apagar_senha_apaga_o_ticket_mas_nao_o_cliente(self):
        ticket = Ticket.emitir('João', 'normal')
        cliente_id = ticket.cliente_id
        ticket.senha.delete()
        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(Cliente.objects.filter(pk=cliente_id).exists())

    def test_cliente_pode_ter_varios_tickets(self):
        primeiro = Ticket.emitir('João', 'normal')
        segundo = Ticket.emitir('João', 'normal')
        segundo.cliente = primeiro.cliente
        segundo.save()
        self.assertEqual(primeiro.cliente.ticket_set.count(), 2)


class EmissaoTests(BaseTestCase):
    """Regras do totem."""

    def test_codigos_sempre_crescem_mesmo_com_buracos(self):
        Senha.objects.create(codigo='A0011')
        Senha.objects.create(codigo='A0005')
        self.assertEqual(Senha.proximo_codigo(), 'A0012')

    def test_totem_cria_cliente_senha_e_ticket(self):
        resposta = self.client.post(url('totem'), {'nome': 'João', 'tipo_prioridade': 'idoso'})
        ticket = Ticket.objects.get()
        self.assertRedirects(resposta, url('senha_emitida', ticket.pk))
        self.assertEqual(ticket.senha.codigo, 'A0001')
        self.assertEqual(ticket.cliente.tipo_prioridade, 'idoso')

    def test_totem_nao_emite_em_feriado_ativo(self):
        Data.objects.create(usuario=self.admin, dia=timezone.localdate(), feriado='Natal')
        self.client.post(url('totem'), {'nome': 'João', 'tipo_prioridade': 'normal'})
        self.assertEqual(Ticket.objects.count(), 0)

    def test_totem_emite_se_o_feriado_estiver_inativo(self):
        Data.objects.create(usuario=self.admin, dia=timezone.localdate(),
                            feriado='Natal', status='inativo')
        self.client.post(url('totem'), {'nome': 'João', 'tipo_prioridade': 'normal'})
        self.assertEqual(Ticket.objects.count(), 1)


class FilaTests(BaseTestCase):
    """Regras da fila de atendimento."""

    def setUp(self):
        super().setUp()
        self.sessao = SessaoMesa.entrar(self.user, self.mesa1.pk)

    def test_prioritario_passa_na_frente_e_chegada_desempata(self):
        normal = Ticket.emitir('Normal', 'normal').senha
        idoso = Ticket.emitir('Idoso', 'idoso').senha
        gestante = Ticket.emitir('Gestante', 'gestante').senha
        self.assertEqual(list(Senha.objects.fila_de_hoje()), [idoso, gestante, normal])

    def test_senha_de_outro_dia_nao_entra_na_fila(self):
        ticket = Ticket.emitir('Ontem', 'normal')
        Ticket.objects.filter(pk=ticket.pk).update(data=timezone.localdate() - timedelta(days=1))
        self.assertIsNone(self.sessao.chamar_proxima())

    def test_chamar_registra_mesa_e_finaliza_o_atendimento_anterior(self):
        primeira = Ticket.emitir('A', 'normal').senha
        segunda = Ticket.emitir('B', 'normal').senha

        self.assertEqual(self.sessao.chamar_proxima(), primeira)
        primeira.refresh_from_db()
        self.assertEqual(primeira.status, 'chamada')
        self.assertEqual(primeira.ticket.sessao_mesa, self.sessao)

        self.assertEqual(self.sessao.chamar_proxima(), segunda)
        primeira.refresh_from_db()
        self.assertEqual(primeira.status, 'atendida')

    def test_fila_vazia_nao_finaliza_quem_esta_em_atendimento(self):
        senha = Ticket.emitir('A', 'normal').senha
        self.sessao.chamar_proxima()
        self.assertIsNone(self.sessao.chamar_proxima())
        senha.refresh_from_db()
        self.assertEqual(senha.status, 'chamada')

    def test_chamar_sem_mesa_nao_chama_ninguem(self):
        senha = Ticket.emitir('A', 'normal').senha
        self.client.force_login(self.outro)
        self.client.post(url('chamar_senha'))
        senha.refresh_from_db()
        self.assertEqual(senha.status, 'aguardando')

    def test_filtro_da_tela_nao_altera_a_ordem_do_botao_chamar(self):
        idoso = Ticket.emitir('Idoso', 'idoso').senha
        Ticket.emitir('Normal', 'normal')
        self.client.force_login(self.user)
        resposta = self.client.get(url('fila'), {'prioridade': 'normal'})
        self.assertNotIn(idoso, resposta.context['senhas_aguardando'])
        self.client.post(url('chamar_senha'))
        idoso.refresh_from_db()
        self.assertEqual(idoso.status, 'chamada')

    def test_voltar_para_aguardando_limpa_o_registro_da_chamada(self):
        senha = Ticket.emitir('A', 'normal').senha
        self.sessao.chamar_proxima()
        senha.refresh_from_db()
        senha.ajustar_status('aguardando')
        senha.ticket.refresh_from_db()
        self.assertIsNone(senha.ticket.hora_atendimento)
        self.assertIsNone(senha.ticket.sessao_mesa)


class PainelTests(BaseTestCase):
    def test_painel_segue_a_ordem_de_chamada_e_nao_a_de_emissao(self):
        sessao = SessaoMesa.entrar(self.user, self.mesa1.pk)
        normal = Ticket.emitir('Normal', 'normal').senha
        idoso = Ticket.emitir('Idoso', 'idoso').senha
        sessao.chamar_proxima()  # chama o idoso, emitido depois
        sessao.chamar_proxima()  # chama o normal, emitido antes

        dados = self.client.get(url('painel_tv_json')).json()
        self.assertEqual(dados['senha_atual'], {'codigo': normal.codigo, 'mesa': 1})
        self.assertEqual(dados['ultimas_senhas'], [{'codigo': idoso.codigo, 'mesa': 1}])

    def test_senha_finalizada_continua_nas_ultimas(self):
        sessao = SessaoMesa.entrar(self.user, self.mesa1.pk)
        senha = Ticket.emitir('A', 'normal').senha
        sessao.chamar_proxima()
        sessao.finalizar_atendimento()

        dados = self.client.get(url('painel_tv_json')).json()
        self.assertIsNone(dados['senha_atual'])
        self.assertEqual(dados['ultimas_senhas'][0]['codigo'], senha.codigo)

    def test_pagina_do_painel_abre_sem_login(self):
        self.assertEqual(self.client.get(url('painel_tv')).status_code, 200)


class MesaTests(BaseTestCase):
    """Regras de ocupação de mesas."""

    def test_duas_pessoas_nao_usam_a_mesma_mesa(self):
        SessaoMesa.entrar(self.user, self.mesa1.pk)
        with self.assertRaises(RegraDeNegocioError):
            SessaoMesa.entrar(self.outro, self.mesa1.pk)

    def test_nao_entra_em_mesa_desativada(self):
        self.mesa1.alternar_status()
        with self.assertRaises(RegraDeNegocioError):
            SessaoMesa.entrar(self.user, self.mesa1.pk)

    def test_trocar_de_mesa_encerra_a_sessao_anterior(self):
        SessaoMesa.entrar(self.user, self.mesa1.pk)
        SessaoMesa.entrar(self.user, self.mesa2.pk)
        self.assertEqual(self.user.sessao_ativa.mesa, self.mesa2)
        self.assertIsNone(self.mesa1.sessao_aberta)

    def test_nao_desativa_nem_deleta_mesa_em_uso(self):
        SessaoMesa.entrar(self.user, self.mesa1.pk)
        with self.assertRaises(RegraDeNegocioError):
            self.mesa1.alternar_status()
        self.client.force_login(self.admin)
        self.client.post(url('deletar_mesa', self.mesa1.pk))
        self.assertTrue(Mesa.objects.filter(pk=self.mesa1.pk).exists())

    def test_logout_libera_a_mesa(self):
        SessaoMesa.entrar(self.user, self.mesa1.pk)
        self.client.force_login(self.user)
        self.client.post(url('logout'))
        self.assertIsNone(self.mesa1.sessao_aberta)

    def test_numero_de_mesa_nao_pode_repetir(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(url('editar_mesa', self.mesa2.pk), {'numero': 1})
        self.assertEqual(resposta.status_code, 200)  # volta ao formulário com o erro
        self.mesa2.refresh_from_db()
        self.assertEqual(self.mesa2.numero, 2)

    def test_tela_mostra_acao_correta_de_ativar_e_desativar(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url('mesas')), 'DESATIVAR')
        self.assertNotContains(self.client.get(url('mesas')), '>ATIVAR<')


class AcessoTests(BaseTestCase):
    """Requisito 3: dois níveis de acesso (admin e user)."""

    ROTAS_ADMIN = ['mesas', 'mensagens', 'criar_mensagem', 'notas', 'criar_nota', 'datas', 'criar_data']
    ROTAS_USER = ['fila', 'historico', 'notificacoes']

    def test_visitante_vai_para_o_login(self):
        for rota in self.ROTAS_ADMIN + self.ROTAS_USER:
            resposta = self.client.get(url(rota))
            self.assertEqual(resposta.status_code, 302, rota)
            self.assertIn(url('login'), resposta.url, rota)

    def test_user_nao_entra_nas_telas_de_admin(self):
        self.client.force_login(self.user)
        for rota in self.ROTAS_ADMIN:
            self.assertRedirects(self.client.get(url(rota)), url('fila'), msg_prefix=rota)

    def test_user_entra_nas_telas_de_atendimento(self):
        self.client.force_login(self.user)
        for rota in self.ROTAS_USER:
            self.assertEqual(self.client.get(url(rota)).status_code, 200, rota)

    def test_admin_entra_em_todas_as_telas(self):
        self.client.force_login(self.admin)
        for rota in self.ROTAS_ADMIN + self.ROTAS_USER:
            self.assertEqual(self.client.get(url(rota)).status_code, 200, rota)

    def test_user_nao_altera_mesa_nem_senha(self):
        senha = Ticket.emitir('A', 'normal').senha
        self.client.force_login(self.user)
        self.client.post(url('deletar_mesa', self.mesa1.pk))
        self.client.post(url('deletar_senha', senha.pk))
        self.client.post(url('alternar_mesa', self.mesa1.pk))
        self.client.post(url('criar_mesa'))
        self.assertEqual(Mesa.objects.count(), 2)
        self.assertTrue(Senha.objects.filter(pk=senha.pk).exists())
        self.mesa1.refresh_from_db()
        self.assertEqual(self.mesa1.status, 'disponivel')

    def test_get_nunca_altera_dados(self):
        self.client.force_login(self.admin)
        for rota in ['deletar_mesa', 'alternar_mesa']:
            self.assertEqual(self.client.get(url(rota, self.mesa1.pk)).status_code, 405, rota)
        self.assertEqual(self.client.get(url('criar_mesa')).status_code, 405)
        self.assertEqual(Mesa.objects.count(), 2)

    def test_superusuario_vira_administrador(self):
        chefe = Usuario.objects.create_superuser('root', password='x')
        self.assertTrue(chefe.is_adm)

    def test_nao_le_notificacao_de_outra_pessoa(self):
        mensagem = Mensagem.objects.create(usuario=self.admin, conteudo='Oi')
        alheia = Notificacao.objects.create(usuario=self.outro, mensagem=mensagem)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url('ler_notificacao', alheia.pk)).status_code, 404)
        alheia.refresh_from_db()
        self.assertFalse(alheia.visualizada)


class NotificacaoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_mensagem_notifica_so_os_atendentes(self):
        self.client.post(url('criar_mensagem'), {'conteudo': 'Reunião'})
        self.assertEqual(Notificacao.objects.count(), 2)
        self.assertFalse(Notificacao.objects.filter(usuario=self.admin).exists())

    def test_data_tambem_notifica_os_atendentes(self):
        self.client.post(url('criar_data'), {'dia': '2030-12-25', 'feriado': 'Natal', 'status': 'ativo'})
        self.assertEqual(Notificacao.objects.filter(data__isnull=False).count(), 2)

    def test_data_repetida_e_recusada(self):
        dados = {'dia': '2030-12-25', 'feriado': 'Natal', 'status': 'ativo'}
        self.client.post(url('criar_data'), dados)
        resposta = self.client.post(url('criar_data'), dados)
        self.assertContains(resposta, 'já está cadastrada')
        self.assertEqual(Data.objects.count(), 1)

    def test_lista_nao_repete_as_notificacoes(self):
        self.client.post(url('criar_mensagem'), {'conteudo': 'Um'})
        self.client.post(url('criar_mensagem'), {'conteudo': 'Dois'})
        self.client.force_login(self.user)
        html = self.client.get(url('notificacoes')).content.decode()
        self.assertEqual(html.count('class="notificacao-item'), 2)

    def test_mensagem_vira_lida_quando_todos_leem(self):
        self.client.post(url('criar_mensagem'), {'conteudo': 'Um'})
        mensagem = Mensagem.objects.get()

        self.client.force_login(self.user)
        self.client.get(url('ler_notificacao', self.user.notificacao_set.get().pk))
        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, 'enviada')

        self.client.force_login(self.outro)
        self.client.get(url('ler_notificacao', self.outro.notificacao_set.get().pk))
        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status, 'lida')


class FiltroTests(BaseTestCase):
    """Requisito 2: filtros."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.sessao = SessaoMesa.entrar(self.user, self.mesa1.pk)
        self.joao = Ticket.emitir('João', 'normal')
        self.maria = Ticket.emitir('Maria', 'idoso')
        self.sessao.chamar_proxima()
        self.sessao.chamar_proxima()
        # O atendimento do João passa a ser de 10 dias atrás.
        self.dez_dias = timezone.localdate() - timedelta(days=10)
        Ticket.objects.filter(pk=self.joao.pk).update(data=self.dez_dias)

    def historico(self, **filtros):
        return list(self.client.get(url('historico'), filtros).context['tickets'])

    def test_historico_abre_mostrando_so_hoje(self):
        self.assertEqual(self.historico(), [self.maria])

    def test_filtro_todo_o_periodo(self):
        self.assertEqual(len(self.historico(periodo='')), 2)

    def test_filtro_por_intervalo_de_datas(self):
        self.assertEqual(
            self.historico(data_inicio=self.dez_dias.isoformat(), data_fim=self.dez_dias.isoformat()),
            [self.joao],
        )

    def test_filtro_por_nome_prioridade_mesa_e_atendente(self):
        self.assertEqual(self.historico(periodo='', busca='joão'), [self.joao])
        self.assertEqual(self.historico(periodo='', prioridade='idoso'), [self.maria])
        self.assertEqual(self.historico(periodo='', mesa=self.mesa2.pk), [])
        self.assertEqual(len(self.historico(periodo='', atendente=self.user.pk)), 2)

    def test_intervalo_invertido_mostra_erro(self):
        resposta = self.client.get(url('historico'), {'data_inicio': '2030-02-01', 'data_fim': '2030-01-01'})
        self.assertContains(resposta, 'não pode ser depois')

    def test_filtros_das_telas_de_admin(self):
        self.client.force_login(self.admin)
        Data.objects.create(usuario=self.admin, dia='2030-12-25', feriado='Natal')
        Data.objects.create(usuario=self.admin, dia='2030-01-01', feriado='Ano Novo')
        resposta = self.client.get(url('datas'), {'busca': 'natal'})
        self.assertEqual(len(resposta.context['datas']), 1)

        resposta = self.client.get(url('mesas'), {'ocupacao': 'ocupada'})
        self.assertEqual(list(resposta.context['mesas']), [self.mesa1])


class TelasTests(BaseTestCase):
    """Garante que os formulários de edição abrem e salvam."""

    def test_formularios_do_admin(self):
        self.client.force_login(self.admin)
        senha = Ticket.emitir('João', 'normal').senha
        self.assertEqual(self.client.get(url('editar_senha', senha.pk)).status_code, 200)
        self.client.post(url('editar_senha', senha.pk), {
            'status': 'atendida', 'nome': 'João Silva', 'tipo_prioridade': 'pcd',
        })
        senha.refresh_from_db()
        self.assertEqual(senha.status, 'atendida')
        self.assertEqual(senha.ticket.cliente.nome, 'João Silva')
        self.assertEqual(senha.ticket.cliente.tipo_prioridade, 'pcd')

        self.assertEqual(self.client.get(url('editar_mesa', self.mesa1.pk)).status_code, 200)
        data = Data.objects.create(usuario=self.admin, dia='2030-12-25')
        self.assertEqual(self.client.get(url('editar_data', data.pk)).status_code, 200)

    def test_nome_em_branco_e_recusado_na_edicao_da_senha(self):
        self.client.force_login(self.admin)
        senha = Ticket.emitir('João', 'normal').senha
        self.client.post(url('editar_senha', senha.pk), {'status': 'chamada', 'nome': '', 'tipo_prioridade': 'normal'})
        senha.refresh_from_db()
        self.assertEqual(senha.ticket.cliente.nome, 'João')

    def test_home_e_login_abrem_sem_login(self):
        self.assertEqual(self.client.get(url('home')).status_code, 200)
        self.assertEqual(self.client.get(url('login')).status_code, 200)
        self.assertEqual(self.client.get(url('totem')).status_code, 200)
