from django.shortcuts import redirect
from functools import wraps


def somente_adm(view_func):
    """
    Decorator que só permite acesso se o usuário for ADM.
    Se não for, redireciona para a fila.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_adm:
            return redirect('swgfApp:fila')
        return view_func(request, *args, **kwargs)
    return wrapper