from dataclasses import dataclass, field
from pathlib import Path
from photos_creation_date_overwrite import INPUT_DIR, OUTPUT_DIR
import piexif
import re
from datetime import datetime
import shutil

@dataclass
class UpdateReport:
    updated: int = field(default=0, init=False)
    added: int = field(default=0, init=False)
    failed: int = field(default=0, init=False)
    preserved: int = field(default=0, init=False)


    def as_text(self) -> str:
        return (
            f"Updated: {self.updated}\n"
            f"Added: {self.added}\n"
            f"Failed: {self.failed}\n"
            f"Preserved: {self.preserved}\n"
        )

def main():
    # Process all .jpg files in input directory
    jpg_files = _read_files()
    if not jpg_files:
        print("No .jpg files found in input directory")
        return

    # create output subdirectory with timestamp
    output_subdir = OUTPUT_DIR / datetime.now().strftime('%Y%m%d_%H%M%S')
    output_subdir.mkdir(parents=True, exist_ok=True)

    report = UpdateReport()
    for image_path in jpg_files:
        print(f"\nProcessing: {image_path.name}")
        output_path = output_subdir / image_path.name

        # Extract date from filename
        filename_date = _extract_date_from_filename(image_path.name)
        if not filename_date:
            print(f"  Could not extract date from filename: {image_path.name}")
            # Copy file as-is to output directory
            shutil.copy2(image_path, output_path)
            continue

        print(f"  Date from filename: {filename_date.strftime('%Y-%m-%d')}")

        # Get EXIF date
        exif_date = _get_exif_date(image_path)
        if exif_date:
            print(f"  Date from EXIF: {exif_date.strftime('%Y-%m-%d %H:%M:%S')}")

            # Compare dates (only compare the date part, not time)
            if filename_date.date() == exif_date.date():
                print("  Dates match - copying file without changes")
                shutil.copy2(image_path, output_path)
                report.preserved += 1
            else:
                print("  Dates don't match - updating EXIF data")
                if _update_exif_date(image_path, filename_date, output_path):
                    print("  Successfully updated EXIF date")
                    report.updated += 1
                else:
                    print("  Failed to update EXIF date - copying original")
                    shutil.copy2(image_path, output_path)
                    report.failed += 1
        else:
            print("  No EXIF date found - adding date from filename")
            if _update_exif_date(image_path, filename_date, output_path):
                print("  Successfully added EXIF date")
                report.added += 1
            else:
                print("  Failed to add EXIF date - copying original")
                shutil.copy2(image_path, output_path)
                report.failed += 1

    print(f"\nProcessing complete. Check the '{output_subdir}' directory for results.")
    print("Update Report:")
    print(report.as_text())

def _read_files() -> list[Path]:
    files = (list(INPUT_DIR.glob('*.jpg')) + list(INPUT_DIR.glob('*.JPG')) +
             list(INPUT_DIR.glob('*.jpeg')) + list(INPUT_DIR.glob('*.JPEG')))
    print(f"Found {len(files)} image(s) to process")
    return files

def _extract_date_from_filename(filename) -> datetime | None:
    """Extract date from filename.

    Accepted patterns like:
    - IMG-20201107-WA0029.jpg
    - IMG_20201107_WA0029.jpg
    """
    pattern = r'IMG[-_](\d{8})[-_]'
    match = re.search(pattern, filename)
    if match:
        date_str = match.group(1)
        # Parse YYYYMMDD format
        return datetime.strptime(date_str, '%Y%m%d')
    return None

def _get_exif_date(image_path):
    """Get the date taken from EXIF data"""
    try:
        exif_dict = piexif.load(str(image_path))

        # Check if EXIF section exists
        if 'Exif' not in exif_dict:
            print(f"  No EXIF section found in {image_path.name}")
            return None

        if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            date_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode('utf-8')
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        elif '0th' in exif_dict and piexif.ImageIFD.DateTime in exif_dict['0th']:
            date_str = exif_dict['0th'][piexif.ImageIFD.DateTime].decode('utf-8')
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        else:
            print(f"  No date fields found in EXIF data for {image_path.name}")

    except Exception as e:
        print(f"Error reading EXIF data from {image_path}: {e}")
    return None

def _update_exif_date(image_path, new_date, output_path):
    """Update the EXIF date and save to output path"""
    try:
        # Load existing EXIF data
        exif_dict = piexif.load(str(image_path))

        # Initialize EXIF section if it doesn't exist
        if 'Exif' not in exif_dict:
            exif_dict['Exif'] = {}
        if '0th' not in exif_dict:
            exif_dict['0th'] = {}

        # Format date for EXIF (YYYY:MM:DD HH:MM:SS)
        date_str = new_date.strftime('%Y:%m:%d 09:00:00')

        # Update date fields
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = date_str.encode('utf-8')
        exif_dict['0th'][piexif.ImageIFD.DateTime] = date_str.encode('utf-8')
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = date_str.encode('utf-8')

        # Convert back to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Save image with updated EXIF
        piexif.insert(exif_bytes, str(image_path), str(output_path))

        return True
    except Exception as e:
        print(f"Error updating EXIF data for {image_path}: {e}")
        return False


if __name__ == "__main__":
    main()