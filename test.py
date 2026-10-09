from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URL = "https://refundselection.com/refundselection/#/welcome/continue"
SCHOOL = "Cuyahoga Community College"

students_file = Path("students.txt")
results_file = Path("results.txt")

BATCH_SIZE = 1000
MAX_ATTEMPTS = 3


def select_school(page):
    school_field = page.get_by_label("School name")

    school_field.wait_for(
        state="visible",
        timeout=10000
    )

    school_field.click()
    school_field.fill(SCHOOL)

    # Reduced from 1500 ms
    page.wait_for_timeout(500)

    school_option = page.get_by_text(
        SCHOOL,
        exact=True
    )

    school_option.wait_for(
        state="visible",
        timeout=5000
    )

    school_option.click()


def reset_form(page):
    """
    Return to the verification form without reopening the browser
    or creating a new page.
    """

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=30000
    )

    # Reduced from 2000 ms
    page.wait_for_timeout(750)

    select_school(page)


def check_student(page, email):
    student_id = email.split("@")[0]

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print()
        print(f"Attempt {attempt}/{MAX_ATTEMPTS} for {email}")

        try:
            # -------------------------------------------------
            # Only reset/navigate if necessary
            # -------------------------------------------------

            # After the previous student, the page may be on the
            # result/profile page. Return to the form.
            #
            # This is much cheaper than creating a new page/browser,
            # while still ensuring the correct form is displayed.

            if "#/welcome/continue" not in page.url.lower():
                reset_form(page)

            else:
                # Make sure the form is actually ready.
                try:
                    page.get_by_label(
                        "School name"
                    ).wait_for(
                        state="visible",
                        timeout=3000
                    )
                except PlaywrightTimeoutError:
                    reset_form(page)

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
                timeout=10000
            )

            email_field.wait_for(
                state="visible",
                timeout=10000
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
                timeout=10000
            )

            verify_button.click()

            # -------------------------------------------------
            # Wait for result
            # -------------------------------------------------

            for _ in range(20):

                current_url = page.url.lower()

                # VERIFIED
                if "#/profile" in current_url:
                    return student_id, "VERIFIED"

                text = page.locator(
                    "body"
                ).inner_text().lower()

                if "we found your information" in text:
                    return student_id, "VERIFIED"

                # NOT MATCHED
                if "still no match" in text:
                    return student_id, "NOT MATCHED"

                if (
                    "we weren't able to verify your information"
                    in text
                ):
                    return student_id, "NOT MATCHED"

                # EXISTING ACCOUNT
                if "we couldn't match your information" in text:
                    return student_id, "EXISTING ACCOUNT"

                # Reduced from 1000 ms
                page.wait_for_timeout(500)

            print("No recognizable result appeared.")

            if attempt < MAX_ATTEMPTS:
                print("Retrying this student...")
                page.wait_for_timeout(1500)

                # Make sure the next attempt starts from the form.
                reset_form(page)

        except Exception as error:

            print()
            print(f"Attempt {attempt} failed: {error}")

            if attempt < MAX_ATTEMPTS:

                print("Retrying the same student...")

                page.wait_for_timeout(1500)

                try:
                    reset_form(page)
                except Exception:
                    pass

    print(
        f"Could not determine a result for {email} "
        f"after {MAX_ATTEMPTS} attempts."
    )

    return student_id, "UNKNOWN"


def remove_student_from_file(email):
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
    with results_file.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"{student_id} | {email} | {result}\n"
        )


# -------------------------------------------------------------
# Read students
# -------------------------------------------------------------

students = [
    line.strip()
    for line in students_file.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]


if not students:

    print()
    print("=" * 55)
    print("NO STUDENTS")
    print("=" * 55)
    print("students.txt is empty.")

    input("\nPress Enter to close...")

    raise SystemExit


# -------------------------------------------------------------
# Select batch
# -------------------------------------------------------------

batch = students[:BATCH_SIZE]

print()
print("=" * 55)
print("REFUND CHECKER")
print("=" * 55)

print(f"Total emails in students.txt: {len(students)}")
print(f"Emails in this batch: {len(batch)}")
print(
    f"Emails remaining after this batch: "
    f"{max(0, len(students) - len(batch))}"
)
print(f"Maximum attempts per student: {MAX_ATTEMPTS}")

print("=" * 55)


with sync_playwright() as p:

    browser = None

    try:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        # ---------------------------------------------------------
        # LOAD THE WEBSITE ONCE
        # ---------------------------------------------------------

        print()
        print("Opening verification page...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(750)

        print("Selecting school...")

        select_school(page)

        print("Verification page ready.")

        processed_count = 0

        # ---------------------------------------------------------
        # PROCESS BATCH
        # ---------------------------------------------------------

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
                # REMOVE STUDENT IMMEDIATELY
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

                print(f"Student: {email}")
                print(f"Error: {error}")

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
            # Short pause between students
            # -----------------------------------------------------

            if number < len(batch):

                # Reduced from 5 seconds
                print("Waiting 2 seconds before next student...")
                page.wait_for_timeout(2000)

        # ---------------------------------------------------------
        # Summary
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

        print(f"Error: {error}")

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
