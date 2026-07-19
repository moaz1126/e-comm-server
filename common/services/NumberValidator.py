from decimal import Decimal
import math



class NumberValidator:
    """
    A utility class where methods return None if valid, 
    or an error message string if invalid.
    """

    @staticmethod
    def _coerce_to_numeric(val):
        """Helper: Converts input to numeric. Returns (value, error_message)."""        
        if isinstance(val, (int, float, Decimal)):
            return val, None

        if isinstance(val, str):
            try:
                return float(val), None
            except ValueError:
                return None, f"'{val}' is not a valid numeric representation."
        
        return None, f"Type '{type(val).__name__}' is not supported."

    @staticmethod
    def is_number(value) -> str | None:
        """Returns None if valid, error message otherwise."""
        _, error = NumberValidator._coerce_to_numeric(value)
        return error

    @staticmethod
    def is_equal(value, target, tolerance=None) -> str | None:
        v, err_v = NumberValidator._coerce_to_numeric(value)
        t, err_t = NumberValidator._coerce_to_numeric(target)
        
        if err_v: return f"Value error: {err_v}"
        if err_t: return f"Target error: {err_t}"
        
        if tolerance is not None:
            if math.isclose(v, t, abs_tol=tolerance):
                return None
            return f"{value} is not equal to {target} (within tolerance {tolerance})"
            
        if v == t:
            return None
        return f"unsupported values, {value} is not equal to {target}"

    @staticmethod
    def is_greater_than(value, target) -> str | None:
        v, err_v = NumberValidator._coerce_to_numeric(value)
        t, err_t = NumberValidator._coerce_to_numeric(target)
        
        if err_v: return f"Value error: {err_v}"
        if err_t: return f"Target error: {err_t}"
        
        if v > t:
            return None
        return f"maximum value exceeded ({target})"

    @staticmethod
    def is_less_than(value, target) -> str | None:
        v, err_v = NumberValidator._coerce_to_numeric(value)
        t, err_t = NumberValidator._coerce_to_numeric(target)
        
        if err_v: return f"Value error: {err_v}"
        if err_t: return f"Target error: {err_t}"
        
        if v < t:
            return None
        return f"minimal value exceeded ({target})"
