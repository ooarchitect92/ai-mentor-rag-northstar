# Enrollment operations

- `create_enrollment_workbook.py` creates a safe Excel template. Existing files
  require the explicit `--force` option.
- `set_student_courses.py` replaces one student's active course set using a
  full international WhatsApp number and an atomic workbook save.

Normal enrollment changes should be made through the admin dashboard so they
are validated and audited.
