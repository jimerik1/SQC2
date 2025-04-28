import numpy as np

def safe_inverse(mat: np.ndarray, ridge: float = 1e-9) -> np.ndarray:
    """
    Return (mat + ridge*I)⁻¹  with graceful fallback.

    Raises
    ------
    np.linalg.LinAlgError
        If the matrix is still singular after regularisation.
    """
    eye = np.eye(mat.shape[0], dtype=mat.dtype)
    try:
        return np.linalg.inv(mat + ridge * eye)
    except np.linalg.LinAlgError:
        # second attempt with larger ridge
        try:
            return np.linalg.inv(mat + ridge * 1e3 * eye)
        except np.linalg.LinAlgError as err:
            raise np.linalg.LinAlgError("Normal matrix singular – "
                                        "survey geometry too weak") from err