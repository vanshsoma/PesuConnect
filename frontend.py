import mysql.connector
import getpass
import datetime
import os
from dotenv import load_dotenv

# --- DATABASE CONFIGURATION ---
load_dotenv()  # Load variables from .env file

DB_CONFIG = {
    'host': os.environ.get('DB_HOST'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME')
}
# ------------------------------


def connect_to_db():
    """Establishes a connection to the database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

# --- AUTHENTICATION FUNCTIONS ---

def student_login(conn):
    """Handles the student login process."""
    print("\n--- PESUConnect Login ---")
    email = input("Email (@pesu.edu): ")
    password = getpass.getpass("Password (hidden): ")

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('sp_StudentLogin', [email, password])
        
        user = None
        for result in cursor.stored_results():
            user = result.fetchone()
            
        cursor.close()
        
        if user:
            print(f"\nLogin successful! Welcome, {user['name']}.")
            return user
        else:
            print("\nLogin failed: Invalid credentials.")
            return None
            
    except mysql.connector.Error as err:
        print(f"Login error: {err}")
        return None

def student_register(conn):
    """Handles the new student registration process."""
    print("\n--- PESUConnect Sign Up ---")
    try:
        email = input("Email (@pesu.edu): ")
        name = input("Full Name: ")
        password = getpass.getpass("Password (hidden): ")
        confirm_password = getpass.getpass("Confirm Password (hidden): ")
        
        if password != confirm_password:
            print("\nError: Passwords do not match.")
            return

        phone = input("Phone Number (optional): ")
        department = input("Department (e.g., CSE): ")
        year = int(input("Year of Study (e.g., 2): "))

        cursor = conn.cursor()
        insert_query = """
        INSERT INTO Student (name, email, password, phone_number, department, year_of_study)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (name, email, password, phone, department, year))
        conn.commit()
        
        print(f"\nRegistration successful! Welcome, {name}. Please log in.")
        print("Tip: After logging in, visit 'Manage My Skills' to build your profile.")
        cursor.close()

    except mysql.connector.Error as err:
        print(f"\nError registering: {err}")
        conn.rollback()
    except ValueError:
        print("\nError: Year of study must be a number.")
        conn.rollback()

# --- PROJECT & APPLICATION FUNCTIONS ---

def view_projects(conn, user_id):
    """Fetches and displays all 'Open' projects, with an option to apply."""
    print("\n--- Available Projects ---")
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('sp_SearchProjects', [None, 'Open'])

        projects = []
        for result in cursor.stored_results():
            projects = result.fetchall()
            
        cursor.close()

        if not projects:
            print("No open projects found.")
            return

        for proj in projects:
            deadline_date = proj['deadline'].strftime('%Y-%m-%d')
            print("-------------------------")
            print(f"  ID: {proj['project_id']}")
            print(f"  Title: {proj['title']}")
            print(f"  Owner: {proj['owner_name']}")
            print(f"  Deadline: {deadline_date}")
            print(f"  Description: {proj['description']}")
        print("-------------------------")
        
        while True:
            choice = input("\nEnter a Project ID to apply, or (q) to go back: ").strip().lower()
            if choice == 'q':
                break
            try:
                project_id = int(choice)
                if project_id not in [p['project_id'] for p in projects]:
                    print("Error: Invalid Project ID from the list.")
                else:
                    apply_for_project(conn, user_id, project_id)
                    break 
            except ValueError:
                print("Error: Please enter a number or 'q'.")
            
    except mysql.connector.Error as err:
        print(f"Error fetching projects: {err}")

def apply_for_project(conn, user_id, project_id):
    """Applies the logged-in user to a project."""
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_CreateApplication', [user_id, project_id])
        conn.commit()
        print("\nSuccess! Your application has been submitted.")
    except mysql.connector.Error as err:
        print(f"\nError applying for project: {err}")
        conn.rollback()

def create_project(conn, user_id):
    """Walks the user through creating a new project."""
    print("\n--- Create a New Project ---")
    try:
        title = input("Project Title: ")
        description = input("Project Description: ")
        
        while True:
            deadline_str = input("Deadline (YYYY-MM-DD): ")
            try:
                deadline = datetime.datetime.strptime(deadline_str, '%Y-%m-%d').date()
                if deadline <= datetime.date.today():
                    print("Error: Deadline must be in the future.")
                else:
                    break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        cursor = conn.cursor()
        cursor.callproc('sp_CreateProject', [user_id, title, description, deadline])
        conn.commit()
        
        print("\nSuccess! Your project has been posted.")
        cursor.close()

    except mysql.connector.Error as err:
        print(f"Error creating project: {err}")
        conn.rollback()

def manage_my_projects(conn, user):
    """Shows a list of projects owned by the user and allows them to manage applications."""
    print("\n--- Manage My Projects ---")
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                p.project_id, 
                p.title, 
                p.status,
                fn_GetProjectApplicationCount(p.project_id) AS pending_apps
            FROM Project p
            WHERE p.student_id = %s
        """
        cursor.execute(query, (user['student_id'],))
        my_projects = cursor.fetchall()

        if not my_projects:
            print("You have not created any projects.")
            cursor.close()
            return

        print("Your projects:")
        for proj in my_projects:
            print(f"  ID: {proj['project_id']} | {proj['title']} ({proj['status']})")
            print(f"  Pending Applications: {proj['pending_apps']}")
            print("  --------------------")
        
        cursor.close()
        
        while True:
            choice = input("\nEnter a Project ID to review applications, or (q) to go back: ").strip().lower()
            if choice == 'q':
                break
            try:
                project_id = int(choice)
                if project_id not in [p['project_id'] for p in my_projects]:
                    print("Error: Invalid Project ID from your list.")
                else:
                    review_applications(conn, project_id)
                    break 
            except ValueError:
                print("Error: Please enter a number or 'q'.")

    except mysql.connector.Error as err:
        print(f"Error fetching your projects: {err}")

def review_applications(conn, project_id):
    """Allows a project owner to review, accept, or reject applications."""
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT a.application_id, a.application_date, s.name AS applicant_name
            FROM Application a
            JOIN Student s ON a.student_id = s.student_id
            WHERE a.project_id = %s AND a.status = 'Pending'
        """
        cursor.execute(query, (project_id,))
        applications = cursor.fetchall()

        if not applications:
            print("\nThere are no pending applications for this project.")
            cursor.close()
            return

        print("\n--- Pending Applications ---")
        for app in applications:
            print(f"  ID: {app['application_id']} | Applicant: {app['applicant_name']} | Date: {app['application_date']}")
        
        cursor.close()

        while True:
            app_id_str = input("\nEnter an Application ID to process, or (q) to go back: ").strip().lower()
            if app_id_str == 'q':
                break
            try:
                app_id = int(app_id_str)
                if app_id not in [a['application_id'] for a in applications]:
                    print("Error: Invalid Application ID from the list.")
                    continue
                
                action = input(f"Accept (a) or Reject (r) application {app_id}? ").strip().lower()
                cursor = conn.cursor()

                if action == 'a':
                    cursor.callproc('sp_AcceptApplication', [app_id])
                    conn.commit()
                    print("\nApplication accepted! A contract has been created.")
                    break
                elif action == 'r':
                    cursor.callproc('sp_RejectApplication', [app_id])
                    conn.commit()
                    print("\nApplication rejected.")
                    break
                else:
                    print("Invalid action. Please enter 'a' or 'r'.")
                
                cursor.close()

            except ValueError:
                print("Error: Please enter a number or 'q'.")
            except mysql.connector.Error as err:
                print(f"Error processing application: {err}")
                conn.rollback()

    except mysql.connector.Error as err:
        print(f"Error fetching applications: {err}")


# --- SKILL FUNCTIONS ---

def view_my_skills(conn, user_id):
    """Fetches and displays the user's current skills."""
    print("\n--- Your Current Skills ---")
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT s.skill_id, s.skill_name, ss.proficiency_level 
            FROM Student_Skill ss
            JOIN Skill s ON ss.skill_id = s.skill_id
            WHERE ss.student_id = %s
        """
        cursor.execute(query, (user_id,))
        skills = cursor.fetchall()
        cursor.close()

        if not skills:
            print("You have not added any skills yet.")
        else:
            for skill in skills:
                print(f"  - ID: {skill['skill_id']} | {skill['skill_name']} ({skill['proficiency_level']})")
        
        return skills
            
    except mysql.connector.Error as err:
        print(f"Error fetching skills: {err}")
        return []

def add_skill(conn, user_id):
    """Adds a new skill to the user's profile.
    If skill doesn't exist in Skill table, it is created.
    """
    print("\n--- Add a New Skill ---")
    try:
        skill_name = input("Enter the name of the skill (e.g., Python, Graphic Design): ").strip()
        if not skill_name:
            print("Skill name cannot be empty.")
            return

        cursor = conn.cursor(dictionary=True)
        
        query_check_user = """
            SELECT ss.student_id
            FROM Student_Skill ss
            JOIN Skill s ON ss.skill_id = s.skill_id
            WHERE ss.student_id = %s AND s.skill_name = %s
        """
        cursor.execute(query_check_user, (user_id, skill_name))
        if cursor.fetchone():
            print(f"Error: You have already added '{skill_name}' to your profile.")
            cursor.close()
            return

        cursor.execute("SELECT skill_id FROM Skill WHERE skill_name = %s", (skill_name,))
        skill = cursor.fetchone()
        
        skill_id = None
        if skill:
            skill_id = skill['skill_id']
        else:
            print(f"'{skill_name}' is a new skill. Adding it to the system...")
            insert_skill_query = "INSERT INTO Skill (skill_name) VALUES (%s)"
            cursor.execute(insert_skill_query, (skill_name,))
            skill_id = cursor.lastrowid
            if not skill_id:
                 cursor.execute("SELECT skill_id FROM Skill WHERE skill_name = %s", (skill_name,))
                 skill = cursor.fetchone()
                 skill_id = skill['skill_id']

        proficiency = ""
        while proficiency not in ('Beginner', 'Intermediate', 'Advanced'):
            proficiency = input(f"Enter your proficiency for {skill_name} (Beginner, Intermediate, Advanced): ").capitalize()
            if proficiency not in ('Beginner', 'Intermediate', 'Advanced'):
                print("Invalid input. Please try again.")

        insert_student_skill_query = """
            INSERT INTO Student_Skill (student_id, skill_id, proficiency_level)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_student_skill_query, (user_id, skill_id, proficiency))
        conn.commit()
        
        print(f"\nSuccess! '{skill_name}' ({proficiency}) added to your profile.")
        cursor.close()

    except mysql.connector.Error as err:
        print(f"\nError adding skill: {err}")
        conn.rollback()
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        conn.rollback()

def update_skill(conn, user_id):
    """Updates the proficiency of an existing skill."""
    print("\n--- Update a Skill ---")
    current_skills = view_my_skills(conn, user_id)
    if not current_skills:
        return

    try:
        skill_id = int(input("\nEnter the ID of the skill to update: "))
        
        if skill_id not in [s['skill_id'] for s in current_skills]:
            print("Error: You have not added this skill.")
            return

        proficiency = ""
        while proficiency not in ('Beginner', 'Intermediate', 'Advanced'):
            proficiency = input("Enter new proficiency (Beginner, Intermediate, Advanced): ").capitalize()
            if proficiency not in ('Beginner', 'Intermediate', 'Advanced'):
                print("Invalid input. Please try again.")
        
        cursor = conn.cursor()
        query = """
            UPDATE Student_Skill 
            SET proficiency_level = %s 
            WHERE student_id = %s AND skill_id = %s
        """
        cursor.execute(query, (proficiency, user_id, skill_id))
        conn.commit()
        print(f"\nSuccess! Skill proficiency updated.")
        cursor.close()
    
    except ValueError:
        print("\nError: Skill ID must be a number.")
        conn.rollback()
    except mysql.connector.Error as err:
        print(f"\nError updating skill: {err}")
        conn.rollback()

def remove_skill(conn, user_id):
    """Removes a skill from the user's profile."""
    print("\n--- Remove a Skill ---")
    current_skills = view_my_skills(conn, user_id)
    if not current_skills:
        return
    
    try:
        skill_id = int(input("\nEnter the ID of the skill to remove: "))

        if skill_id not in [s['skill_id'] for s in current_skills]:
            print("Error: You have not added this skill.")
            return

        cursor = conn.cursor()
        query = "DELETE FROM Student_Skill WHERE student_id = %s AND skill_id = %s"
        cursor.execute(query, (user_id, skill_id))
        conn.commit()
        print(f"\nSuccess! Skill removed from your profile.")
        cursor.close()

    except ValueError:
        print("\nError: Skill ID must be a number.")
        conn.rollback()
    except mysql.connector.Error as err:
        print(f"\nError removing skill: {err}")
        conn.rollback()

def manage_skills(conn, user):
    """Shows the sub-menu for managing skills."""
    while True:
        view_my_skills(conn, user['student_id'])
        print("\n--- Manage Skills Menu ---")
        print("1. Add a new skill")
        print("2. Update a skill's proficiency")
        print("3. Remove a skill")
        print("4. Back to Dashboard")
        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            add_skill(conn, user['student_id'])
        elif choice == '2':
            update_skill(conn, user['student_id'])
        elif choice == '3':
            remove_skill(conn, user['student_id'])
        elif choice == '4':
            break
        else:
            print("\nInvalid choice. Please enter 1-4.")

# --- CONTRACT & REVIEW FUNCTIONS ---

def view_my_active_contracts(conn, user):
    """Shows active contracts and allows project owners to complete them."""
    print("\n--- Your Active Contracts ---")
    user_id = user['student_id']
    owner_contracts_list = [] # To store valid contract IDs
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get contracts where I am the FREELANCER
        print("\nContracts as Freelancer (Working on):")
        query_freelancer = """
            SELECT 
                c.contract_id,
                p.title AS project_title,
                s.name AS project_owner_name,
                c.start_date,
                c.end_date
            FROM Contract c
            JOIN Project p ON c.project_id = p.project_id
            JOIN Student s ON p.student_id = s.student_id
            WHERE 
                c.student_id = %s
                AND p.status = 'In Progress'
        """
        cursor.execute(query_freelancer, (user_id,))
        freelance_contracts = cursor.fetchall()
        
        if not freelance_contracts:
            print("You are not currently working on any projects.")
        else:
            for contract in freelance_contracts:
                print("  --------------------")
                print(f"  Project: {contract['project_title']}")
                print(f"  Owner: {contract['project_owner_name']}")
                print(f"  Contract ID: {contract['contract_id']}")
                print(f"  Start: {contract['start_date']} | End: {contract['end_date']}")
        
        # 2. Get contracts where I am the PROJECT OWNER
        print("\nContracts as Project Owner (Hired for):")
        query_owner = """
            SELECT 
                c.contract_id,
                p.title AS project_title,
                s.name AS freelancer_name,
                c.start_date,
                c.end_date
            FROM Contract c
            JOIN Project p ON c.project_id = p.project_id
            JOIN Student s ON c.student_id = s.student_id
            WHERE 
                p.student_id = %s
                AND p.status = 'In Progress'
        """
        cursor.execute(query_owner, (user_id,))
        owner_contracts = cursor.fetchall()
        
        if not owner_contracts:
            print("You have not hired for any active projects.")
        else:
            for contract in owner_contracts:
                owner_contracts_list.append(contract['contract_id']) # Store valid IDs
                print("  --------------------")
                print(f"  Project: {contract['project_title']}")
                print(f"  Freelancer: {contract['freelancer_name']}")
                print(f"  Contract ID: {contract['contract_id']}")
                print(f"  Start: {contract['start_date']} | End: {contract['end_date']}")
        
        cursor.close()

        # 3. Prompt to complete a contract
        while True:
            choice = input("\nEnter a Contract ID to complete (from your 'Project Owner' list), or (q) to go back: ").strip().lower()
            if choice == 'q':
                break
            try:
                contract_id = int(choice)
                if contract_id not in owner_contracts_list:
                    print("Error: Invalid Contract ID from your 'Project Owner' list.")
                else:
                    complete_contract(conn, contract_id, user)
                    break # Go back to dashboard after completion
            except ValueError:
                print("Error: Please enter a number or 'q'.")

    except mysql.connector.Error as err:
        print(f"Error fetching contracts: {err}")

def complete_contract(conn, contract_id, owner_user):
    """Guides the project owner through completing a contract, leaving a review, and making a payment."""
    print("\n--- Complete Contract ---")
    try:
        # Step 1: Confirm
        confirm = input(f"Are you sure you want to mark Contract {contract_id} as complete? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Action cancelled.")
            return

        # Step 2: Call sp_CompleteContract
        print("Marking contract as complete...")
        cursor = conn.cursor()
        cursor.callproc('sp_CompleteContract', [contract_id])
        conn.commit()
        print("Success! Contract is now 'Completed'.")

        # Step 3: Leave Review
        print("\nPlease leave a review for the freelancer.")
        rating = 0
        while rating < 1 or rating > 5:
            try:
                rating = int(input("Rating (1-5): "))
                if rating < 1 or rating > 5:
                    print("Error: Rating must be between 1 and 5.")
            except ValueError:
                print("Error: Please enter a number.")
        
        review_text = input("Review comment: ")
        
        # --- THIS IS THE FIX ---
        # The parameter order was incorrect. The procedure expects 
        # (text, rating, contract_id, reviewer_id)
        # I have corrected the call to match this.
        cursor.callproc('sp_CreateReview', [review_text, rating, contract_id, owner_user['student_id']])
        conn.commit()
        print("Review submitted. Thank you!")

        # Step 4: Simulate Payment
        print("\nPlease process the payment.")
        amount = 0.0
        while amount <= 0:
            try:
                amount = float(input("Enter payment amount (e.g., 5000.00): "))
                if amount <= 0:
                    print("Error: Amount must be greater than zero.")
            except ValueError:
                print("Error: Please enter a valid amount.")
        
        payment_method = input("Payment Method (e.g., UPI, Card): ")
        
        pay_query = """
            INSERT INTO Payment (amount, payment_date, status, payment_method, contract_id)
            VALUES (%s, CURDATE(), 'Paid', %s, %s)
        """
        cursor.execute(pay_query, (amount, payment_method, contract_id))
        conn.commit()
        
        print("\nPayment processed successfully!")
        print("--- Contract Finished ---")
        cursor.close()

    except mysql.connector.Error as err:
        print(f"\nAn error occurred during completion: {err}")
        conn.rollback()
    except ValueError:
        print("\nInvalid input.")
        conn.rollback()

def view_my_reviews(conn, user):
    """Fetches and displays all reviews for the logged-in user."""
    print("\n--- Your Reviews ---")
    user_id = user['student_id']
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get average rating and count
        cursor.execute("SELECT fn_GetStudentAverageRating(%s) AS avg, fn_GetStudentReviewCount(%s) AS count", (user_id, user_id))
        stats = cursor.fetchone()
        
        if stats:
            print(f"You have {stats['count']} reviews, with an average rating of {stats['avg']:.2f} / 5.00")
        else:
            print("You have 0 reviews.")

        # 2. Get all review text
        query = """
            SELECT r.rating, r.review_text, p.title AS project_title
            FROM Review r
            JOIN Contract c ON r.contract_id = c.contract_id
            JOIN Project p ON c.project_id = p.project_id
            WHERE r.student_id = %s
            ORDER BY c.end_date DESC
        """
        cursor.execute(query, (user_id,))
        reviews = cursor.fetchall()
        
        if reviews:
            print("\n--- Comments ---")
            for review in reviews:
                print("  --------------------")
                print(f"  Project: {review['project_title']}")
                print(f"  Rating: {review['rating']} / 5")
                print(f"  Comment: {review['review_text']}")
        
        cursor.close()
        input("\nPress Enter to return to the Dashboard...")

    except mysql.connector.Error as err:
        print(f"Error fetching reviews: {err}")


# --- MAIN APPLICATION FLOW ---

def show_dashboard(conn, user):
    """Main menu for a logged-in user."""
    while True:
        print("\n--- Dashboard ---")
        print(f"Logged in as: {user['name']} (ID: {user['student_id']})")
        print("1. View Available Projects (and Apply)")
        print("2. Create a New Project")
        print("3. Manage My Projects (Review Applications)")
        print("4. Manage My Skills")
        print("5. View Active Contracts")
        print("6. View My Reviews")
        print("7. Logout")
        choice = input("Enter your choice (1-7): ")
        
        if choice == '1':
            view_projects(conn, user['student_id'])
        elif choice == '2':
            create_project(conn, user['student_id'])
        elif choice == '3':
            manage_my_projects(conn, user)
        elif choice == '4':
            manage_skills(conn, user)
        elif choice == '5':
            view_my_active_contracts(conn, user)
        elif choice == '6':
            view_my_reviews(conn, user)
        elif choice == '7':
            print("\nLogging you out. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please enter a number from 1-7.")

def main():
    """Main function to run the application."""
    conn = connect_to_db()
    if not conn:
        return

    while True:
        print("\nWelcome to PESUConnect")
        print("1. Login")
        print("2. Sign Up")
        print("3. Exit")
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            user = student_login(conn)
            if user:
                show_dashboard(conn, user)
        elif choice == '2':
            student_register(conn)
        elif choice == '3':
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")
        
    conn.close()

# --- Run the app ---
if __name__ == "__main__":
    main()