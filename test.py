from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URL = "https://refundselection.com/refundselection/#/welcome/continue"
SCHOOL = "Nassau Community College"

students_file = Path("students.txt")
results_file = Path("results.txt")

BATCH_SIZE = 250
MAX_ATTEMPTS = 3


def select_school(page):
    school_field = page.get_by_label("School name")

    school_field.wait_for(
        state="visible",
        timeout=15000
    )

    school_field.click()
    school_field.fill(SCHOOL)

    page.wait_for_timeout(1500)

    school_option = page.get_by_text(
        SCHOOL,
        exact=True
    )

    school_option.wait_for(
        state="visible",
        timeout=10000
    )

    school_option.click()


def check_student(page, email):
    student_id = email.split("@")[0]

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print()
        print(f"Attempt {attempt}/{MAX_ATTEMPTS} for {email}")

        try:

            # -------------------------------------------------
            # Open verification page
            # -------------------------------------------------

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=30000
            )

            page.wait_for_timeout(2000)

            # -------------------------------------------------
            # Select school
            # -------------------------------------------------

            try:

                select_school(page)

            except PlaywrightTimeoutError:

                print(
                    "School dropdown did not appear. "
                    "Retrying page..."
                )

                page.reload(
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                page.wait_for_timeout(2500)

                select_school(page)

            # -------------------------------------------------
            # Student fields
            # -------------------------------------------------

            student_field = page.get_by_label(
                "Student ID number"
            )

            email_field = page.get_by_label(
                "School email address"
            )

            student_field.wait_for(
                state="visible",
                timeout=15000
            )

            email_field.wait_for(
                state="visible",
                timeout=15000
            )

            student_field.fill(student_id)
            email_field.fill(email)

            print(f"Student ID: {student_id}")
            print(f"Email: {email}")

            # -------------------------------------------------
            # Verify button
            # -------------------------------------------------

            verify_button = page.get_by_role(
                "button",
                name="Verify my information"
            )

            verify_button.wait_for(
                state="visible",
                timeout=15000
            )

            verify_button.click()

            # Give the website time to respond.
            page.wait_for_timeout(3000)

            # -------------------------------------------------
            # Wait for recognizable result
            # -------------------------------------------------

            for _ in range(30):

                current_url = page.url.lower()

                # -------------------------------------------------
                # VERIFIED
                # -------------------------------------------------

                if "#/profile" in current_url:
                    return student_id, "VERIFIED"

                text = page.locator(
                    "body"
                ).inner_text().lower()

                # -------------------------------------------------
                # VERIFIED
                # -------------------------------------------------

                if "we found your information" in text:
                    return student_id, "VERIFIED"

                # -------------------------------------------------
                # NOT MATCHED
                # -------------------------------------------------

                if "still no match" in text:
                    return student_id, "NOT MATCHED"

                if (
                    "we weren't able to verify your information"
                    in text
                ):
                    return student_id, "NOT MATCHED"

                # -------------------------------------------------
                # EXISTING ACCOUNT
                # -------------------------------------------------

                if "we couldn't match your information" in text:
                    return student_id, "EXISTING ACCOUNT"

                # -------------------------------------------------
                # Check again after 1 second
                # -------------------------------------------------

                page.wait_for_timeout(1000)

            # -------------------------------------------------
            # No recognizable response
            # -------------------------------------------------

            print(
                "No recognizable result appeared."
            )

            if attempt < MAX_ATTEMPTS:

                print(
                    "The website may be lagging. "
                    "Retrying this student..."
                )

                page.wait_for_timeout(3000)

        except Exception as error:

            print()
            print(
                f"Attempt {attempt} failed: {error}"
            )

            if attempt < MAX_ATTEMPTS:

                print(
                    "Retrying the same student..."
                )

                page.wait_for_timeout(3000)

    # ---------------------------------------------------------
    # All attempts failed
    # ---------------------------------------------------------

    print(
        f"Could not determine a result for {email} "
        f"after {MAX_ATTEMPTS} attempts."
    )

    return student_id, "UNKNOWN"


def remove_student_from_file(email):
    """
    Remove one processed email from students.txt.

    The file is rewritten immediately so progress is preserved
    even if the browser or Python program stops afterwards.
    """

    students = [
        line.strip()
        for line in students_file.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    try:
        students.remove(email)

    except ValueError:
        return

    students_file.write_text(
        "\n".join(students)
        + ("\n" if students else ""),
        encoding="utf-8"
    )


def save_result(student_id, email, result):
    """
    Immediately append one completed result to results.txt.
    """

    with results_file.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"{student_id} | {email} | {result}\n"
        )


# -------------------------------------------------------------
# Read all student emails
# -------------------------------------------------------------

students = [
    line.strip()
    for line in students_file.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]


# -------------------------------------------------------------
# No students left
# -------------------------------------------------------------

if not students:

    print()
    print("=" * 55)
    print("NO STUDENTS")
    print("=" * 55)
    print("students.txt is empty.")

    input(
        "\nPress Enter to close..."
    )

    raise SystemExit


# -------------------------------------------------------------
# Select this batch
# -------------------------------------------------------------

batch = students[:BATCH_SIZE]

print()
print("=" * 55)
print("REFUND CHECKER")
print("=" * 55)

print(
    f"Total emails in students.txt: "
    f"{len(students)}"
)

print(
    f"Emails in this batch: "
    f"{len(batch)}"
)

print(
    f"Emails remaining after this batch: "
    f"{max(0, len(students) - len(batch))}"
)

print(
    f"Maximum attempts per student: "
    f"{MAX_ATTEMPTS}"
)

print("=" * 55)


with sync_playwright() as p:

    browser = None

    try:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        processed_count = 0

        for number, email in enumerate(
            batch,
            start=1
        ):

            print()
            print("=" * 55)

            print(
                f"Checking student "
                f"{number}/{len(batch)}: {email}"
            )

            print("=" * 55)

            student_id = email.split("@")[0]

            try:

                # -------------------------------------------------
                # Check the student
                # -------------------------------------------------

                student_id, result = check_student(
                    page,
                    email
                )

                print()
                print(f"Result: {result}")

                # -------------------------------------------------
                # SAVE RESULT IMMEDIATELY
                # -------------------------------------------------

                save_result(
                    student_id,
                    email,
                    result
                )

                print(
                    f"Result saved to: "
                    f"{results_file.resolve()}"
                )

                # -------------------------------------------------
                # REMOVE THIS STUDENT IMMEDIATELY
                # -------------------------------------------------

                remove_student_from_file(
                    email
                )

                print(
                    "Student removed from students.txt"
                )

                processed_count += 1

            except Exception as error:

                print()
                print("=" * 55)
                print("ERROR WHILE CHECKING STUDENT")
                print("=" * 55)

                print(
                    f"Student: {email}"
                )

                print(
                    f"Error: {error}"
                )

                print("=" * 55)

                print()
                print(
                    "This student was NOT removed from "
                    "students.txt."
                )

                print(
                    "The program will stop so the student "
                    "can be retried safely."
                )

                break

            # -----------------------------------------------------
            # Pause between students
            # -----------------------------------------------------

            if number < len(batch):

                print()
                print(
                    "Waiting before next student..."
                )

                page.wait_for_timeout(
                    5000
                )

        # ---------------------------------------------------------
        # Batch summary
        # ---------------------------------------------------------

        print()
        print("=" * 55)
        print("RUN FINISHED")
        print("=" * 55)

        print(
            f"Students successfully processed: "
            f"{processed_count}"
        )

        remaining_count = len([
            line
            for line in students_file.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ])

        print(
            f"Students remaining: "
            f"{remaining_count}"
        )

        print(
            f"Results saved to: "
            f"{results_file.resolve()}"
        )

        print(
            f"Students remaining in: "
            f"{students_file.resolve()}"
        )

        print("=" * 55)

    except Exception as error:

        print()
        print("=" * 55)
        print("PROGRAM STOPPED")
        print("=" * 55)

        print(
            f"Error: {error}"
        )

        print("=" * 55)

    finally:

        if browser:

            try:
                browser.close()

            except Exception:
                pass

        print()
        print("=" * 55)
        print("PROGRAM CLOSED")
        print("=" * 55)

