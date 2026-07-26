import os
from pathlib import Path
import filetype
from PIL import Image
import openpyxl
import tempfile



class DynamicFileValidator:
    def __init__(self, config: dict = None):
        """
        Initializes the validator with dynamic configuration rules.
        
        Example Config Structure:
        {
            "max_size_mb": 5,
            "allowed_mimes": ["image/jpeg", "image/png", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
            "image_rules": {"min_width": 100, "min_height": 100, "max_width": 3840, "max_height": 2160},
            "excel_rules": {"max_sheets": 3, "required_sheets": ["Summary"]},
            "require_utf8": True
        }
        """
        self.config = config or {}

    def validate(self, file_path: str | Path) -> tuple[bool, list[str]]:
        path = Path(file_path)
        errors = []

        # 1. Existence and Type Check
        if not path.exists() or not path.is_file():
            return False, ["File does not exist or is not a valid file path."]

        # 2. File Size Validation (Dynamic)
        file_size_mb = path.stat().st_size / (1024 * 1024)
        max_size = self.config.get("max_size_mb")
        if max_size and file_size_mb > max_size:
            errors.append(f"File size ({file_size_mb:.2f}MB) exceeds the maximum allowed limit of {max_size}MB.")

        # 3. Magic Bytes / MIME Type Detection (Security Check)
        kind = filetype.guess(str(path))
        detected_mime = kind.mime if kind else "application/octet-stream"
        detected_ext = kind.extension if kind else path.suffix.lstrip('.')

        allowed_mimes = self.config.get("allowed_mimes", [])
        if allowed_mimes and detected_mime not in allowed_mimes:
            errors.append(f"Disallowed file type. Detected MIME: '{detected_mime}' (Extension: .{detected_ext})")

        # 4. Content & Type-Specific Dynamic Validations
        if detected_mime.startswith("image/"):
            errors.extend(self._validate_image(path))
        elif detected_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            errors.extend(self._validate_xlsx(path))
        elif detected_mime.startswith("text/") or detected_ext in ["txt", "csv", "json"]:
            errors.extend(self._validate_text(path))

        return len(errors) == 0, errors

    def _validate_image(self, path: Path) -> list[str]:
        errors = []
        rules = self.config.get("image_rules", {})
        try:
            with Image.open(path) as img:
                width, height = img.size
                if "min_width" in rules and width < rules["min_width"]:
                    errors.append(f"Image width ({width}px) is below minimum required {rules['min_width']}px.")
                if "min_height" in rules and height < rules["min_height"]:
                    errors.append(f"Image height ({height}px) is below minimum required {rules['min_height']}px.")
                if "max_width" in rules and width > rules["max_width"]:
                    errors.append(f"Image width ({width}px) exceeds maximum limit of {rules['max_width']}px.")
                if "max_height" in rules and height > rules["max_height"]:
                    errors.append(f"Image height ({height}px) exceeds maximum limit of {rules['max_height']}px.")
        except Exception as e:
            errors.append(f"Corrupted or invalid image file: {str(e)}")
        return errors

    def _validate_xlsx(self, path: Path) -> list[str]:
        errors = []
        rules = self.config.get("excel_rules", {})
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            
            if "max_sheets" in rules and len(wb.sheetnames) > rules["max_sheets"]:
                errors.append(f"Excel contains {len(wb.sheetnames)} sheets, exceeding the maximum of {rules['max_sheets']}.")
            
            if "required_sheets" in rules:
                for req_sheet in rules["required_sheets"]:
                    if req_sheet not in wb.sheetnames:
                        errors.append(f"Required worksheet '{req_sheet}' is missing.")
        except Exception as e:
            errors.append(f"Corrupted or invalid Excel file: {str(e)}")
        return errors

    def _validate_text(self, path: Path) -> list[str]:
        errors = []
        if self.config.get("require_utf8", False):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    f.read(2048) # Read a chunk to test decoding
            except UnicodeDecodeError:
                errors.append("Text file contains invalid characters and is not valid UTF-8.")
            except Exception as e:
                errors.append(f"Error reading text file: {str(e)}")
        return errors

    def validate_bytes(self, file_bytes: bytes, filename: str = "upload") -> tuple[bool, list[str]]:
        """
        Validates raw file bytes coming from an HTTP request by writing 
        them to a secure temporary file for deep inspection.
        """
        suffix = Path(filename).suffix
        temp_path = None
        try:
            # Create a temporary file preserving the original extension for magic byte hints
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            
            # Run the standard validation logic on the temporary file path
            return self.validate(temp_path)
            
        finally:
            # Ensure the temporary file is always cleaned up
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
