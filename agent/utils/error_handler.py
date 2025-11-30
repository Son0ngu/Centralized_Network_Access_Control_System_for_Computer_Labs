"""
Error Handler Utility - Safe execution and critical operation handling.
Vietnam ONLY - Clean implementation.
"""

import logging
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger("utils.error_handler")


class CriticalErrorHandler:
    """
    Proper error handling for critical paths.
    """
    
    @staticmethod
    def safe_execute(
        func: Callable,
        *args,
        error_msg: str = "Operation failed",
        return_on_error: Any = None,
        log_traceback: bool = True,
        **kwargs
    ) -> Any:
        """
        Execute function safely with error handling.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            error_msg: Error message to log on failure
            return_on_error: Value to return on error
            log_traceback: Whether to log full traceback
            **kwargs: Keyword arguments for func
            
        Returns:
            Function result or return_on_error on failure
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if log_traceback:
                logger.error(f"{error_msg}: {e}", exc_info=True)
            else:
                logger.error(f"{error_msg}: {e}")
            return return_on_error
    
    @staticmethod
    def critical_operation(operation_name: str):
        """
        Decorator for critical operations with logging.
        
        Args:
            operation_name: Name of the operation for logging
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                logger.info(f"Starting critical operation: {operation_name}")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"Critical operation completed: {operation_name}")
                    return result
                except Exception as e:
                    logger.error(
                        f"Critical operation failed: {operation_name} - {e}",
                        exc_info=True
                    )
                    raise
            return wrapper
        return decorator
    
    @staticmethod
    def retry_operation(
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        """
        Decorator for retrying operations on failure.
        
        Args:
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries in seconds
            backoff: Multiplier for delay after each retry
            exceptions: Tuple of exceptions to catch and retry
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                from shared.time_utils import sleep
                
                current_delay = delay
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(
                                f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                                f"Retrying in {current_delay:.1f}s..."
                            )
                            sleep(current_delay)
                            current_delay *= backoff
                        else:
                            logger.error(
                                f"All {max_retries + 1} attempts failed for {func.__name__}"
                            )
                
                raise last_exception
            return wrapper
        return decorator