from typing import Callable, Any, List


def chain_exceptions(
    function_to_apply: Callable[..., Any],
    exceptions: List[Exception],
    default_return=None,
    *args,
    **kwargs
) -> Any:
    '''
    Chain exceptions in a way that the function_to_apply is executed and if it raises an exception,
    the exception is appended to the exceptions list and the default_return is returned.
    '''
    try:
        return function_to_apply(*args, **kwargs)
    except Exception as e:
        exceptions.append(e)
        return default_return
