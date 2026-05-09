from contextvars import ContextVar

_current_user = ContextVar('current_user', default=None)
_current_source = ContextVar('current_source', default='django')


def set_current_actor(user, source='django'):
    token_user = _current_user.set(user)
    token_source = _current_source.set(source)
    return token_user, token_source


def reset_current_actor(token_user, token_source):
    _current_user.reset(token_user)
    _current_source.reset(token_source)


def get_current_actor():
    return _current_user.get()


def get_current_source():
    return _current_source.get()
