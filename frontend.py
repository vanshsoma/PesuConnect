import streamlit as st
import mysql.connector
import getpass
import datetime
import os
from dotenv import load_dotenv

# --- DATABASE CONFIGURATION ---
load_dotenv()  # Load variables from .env file (for local development)

# Check if running in Streamlit Cloud (where secrets are set)
if 'DB_HOST' in st.secrets:
    # Use secrets from Streamlit
    DB_CONFIG = {
        'host': st.secrets.get('DB_HOST'),
        'port': st.secrets.get('DB_PORT'),  # <-- Includes your Port fix
        'user': st.secrets.get('DB_USER'),
        'password': st.secrets.get('DB_PASSWORD'),
        'database': st.secrets.get('DB_NAME'),
        'ssl_verify_cert': True,
        'ssl_disabled': False
    }
else:
    # Use .env file (for local development)
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST'),
        'port': os.environ.get('DB_PORT'), # <-- Includes your Port fix
        'user': os.environ.get('DB_USER'),
        'password': os.environ.get('DB_PASSWORD'),
        'database': os.environ.get('DB_NAME'),
        'ssl_verify_cert': True,
        'ssl_disabled': False
    }
# ------------------------------

# --- DATABASE CONNECTION ---
# @st.cache_resource # <-- Removed cache to force fresh connections
def connect_to_db():
    """Establishes a connection to the database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error connecting to database: {err}")
        print(f"Error connecting to database: {err}") # Also print to console
        return None

# --- REFACTORED DATABASE LOGIC (NO UI) ---
# These functions just get or send data to the DB.

def db_student_login(conn, email, password):
    """Handles the student login process."""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('sp_StudentLogin', [email, password])
        user = None
        for result in cursor.stored_results():
            user = result.fetchone()
        cursor.close()
        return user
    except mysql.connector.Error as err:
        st.error(f"Login error: {err}")
        return None

def db_student_register(conn, name, email, password, phone, department, year):
    """Handles the new student registration process."""
    try:
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO Student (name, email, password, phone_number, department, year_of_study)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (name, email, password, phone, department, year))
        conn.commit()
        cursor.close()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error registering: {err}")
        conn.rollback()
        return False

def db_get_open_projects(conn):
    """Fetches all 'Open' projects."""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('sp_SearchProjects', [None, 'Open'])
        projects = []
        for result in cursor.stored_results():
            projects = result.fetchall()
        cursor.close()
        return projects
    except mysql.connector.Error as err:
        st.error(f"Error fetching projects: {err}")
        return []

def db_apply_for_project(conn, user_id, project_id):
    """Applies the logged-in user to a project."""
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_CreateApplication', [user_id, project_id])
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error applying for project: {err}")
        conn.rollback()
        return False

def db_create_project(conn, user_id, title, description, deadline):
    """Creates a new project."""
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_CreateProject', [user_id, title, description, deadline])
        conn.commit()
        cursor.close()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error creating project: {err}")
        conn.rollback()
        return False

def db_get_my_projects(conn, user_id):
    """Gets all projects owned by the user."""
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                p.project_id, p.title, p.status,
                fn_GetProjectApplicationCount(p.project_id) AS pending_apps
            FROM Project p WHERE p.student_id = %s
        """
        cursor.execute(query, (user_id,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        st.error(f"Error fetching your projects: {err}")
        return []

def db_get_pending_applications(conn, project_id):
    """Gets all pending applications for a project."""
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT a.application_id, a.application_date, s.name AS applicant_name
            FROM Application a JOIN Student s ON a.student_id = s.student_id
            WHERE a.project_id = %s AND a.status = 'Pending'
        """
        cursor.execute(query, (project_id,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        st.error(f"Error fetching applications: {err}")
        return []

def db_accept_application(conn, app_id):
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_AcceptApplication', [app_id])
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error accepting application: {err}")
        conn.rollback()
        return False

def db_reject_application(conn, app_id):
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_RejectApplication', [app_id])
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error rejecting application: {err}")
        conn.rollback()
        return False

def db_get_my_skills(conn, user_id):
    """Fetches the user's current skills."""
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT s.skill_id, s.skill_name, ss.proficiency_level 
            FROM Student_Skill ss JOIN Skill s ON ss.skill_id = s.skill_id
            WHERE ss.student_id = %s
        """
        cursor.execute(query, (user_id,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        st.error(f"Error fetching skills: {err}")
        return []

def db_add_skill(conn, user_id, skill_name, proficiency):
    """Adds a new skill to the user's profile."""
    try:
        cursor = conn.cursor(dictionary=True)
        query_check_user = """
            SELECT ss.student_id FROM Student_Skill ss
            JOIN Skill s ON ss.skill_id = s.skill_id
            WHERE ss.student_id = %s AND s.skill_name = %s
        """
        cursor.execute(query_check_user, (user_id, skill_name))
        if cursor.fetchone():
            st.warning(f"You have already added '{skill_name}' to your profile.")
            return False

        cursor.execute("SELECT skill_id FROM Skill WHERE skill_name = %s", (skill_name,))
        skill = cursor.fetchone()
        
        skill_id = None
        if skill:
            skill_id = skill['skill_id']
        else:
            insert_skill_query = "INSERT INTO Skill (skill_name) VALUES (%s)"
            cursor.execute(insert_skill_query, (skill_name,))
            skill_id = cursor.lastrowid
            if not skill_id:
                 cursor.execute("SELECT skill_id FROM Skill WHERE skill_name = %s", (skill_name,))
                 skill_id = cursor.fetchone()['skill_id']
        
        insert_student_skill_query = """
            INSERT INTO Student_Skill (student_id, skill_id, proficiency_level)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_student_skill_query, (user_id, skill_id, proficiency))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error adding skill: {err}")
        conn.rollback()
        return False

def db_update_skill(conn, user_id, skill_id, proficiency):
    try:
        cursor = conn.cursor()
        query = "UPDATE Student_Skill SET proficiency_level = %s WHERE student_id = %s AND skill_id = %s"
        cursor.execute(query, (proficiency, user_id, skill_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error updating skill: {err}")
        conn.rollback()
        return False

def db_remove_skill(conn, user_id, skill_id):
    try:
        cursor = conn.cursor()
        query = "DELETE FROM Student_Skill WHERE student_id = %s AND skill_id = %s"
        cursor.execute(query, (user_id, skill_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error removing skill: {err}")
        conn.rollback()
        return False

def db_get_my_contracts(conn, user_id):
    """Fetches all active contracts for the user."""
    try:
        cursor = conn.cursor(dictionary=True)
        query_freelancer = """
            SELECT c.contract_id, p.title AS project_title, s.name AS project_owner_name, c.start_date, c.end_date
            FROM Contract c
            JOIN Project p ON c.project_id = p.project_id
            JOIN Student s ON p.student_id = s.student_id
            WHERE c.student_id = %s AND p.status = 'In Progress'
        """
        cursor.execute(query_freelancer, (user_id,))
        freelance_contracts = cursor.fetchall()
        
        query_owner = """
            SELECT c.contract_id, p.title AS project_title, s.name AS freelancer_name, c.start_date, c.end_date
            FROM Contract c
            JOIN Project p ON c.project_id = p.project_id
            JOIN Student s ON c.student_id = s.student_id
            WHERE p.student_id = %s AND p.status = 'In Progress'
        """
        cursor.execute(query_owner, (user_id,))
        owner_contracts = cursor.fetchall()
        
        return freelance_contracts, owner_contracts
    except mysql.connector.Error as err:
        st.error(f"Error fetching contracts: {err}")
        return [], []

def db_complete_contract(conn, contract_id):
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_CompleteContract', [contract_id])
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error marking contract complete: {err}")
        conn.rollback()
        return False

def db_create_review(conn, review_text, rating, contract_id, reviewer_id):
    try:
        cursor = conn.cursor()
        cursor.callproc('sp_CreateReview', [review_text, rating, contract_id, reviewer_id])
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error submitting review: {err}")
        conn.rollback()
        return False

def db_create_payment(conn, amount, payment_method, contract_id):
    try:
        cursor = conn.cursor()
        pay_query = "INSERT INTO Payment (amount, payment_date, status, payment_method, contract_id) VALUES (%s, CURDATE(), 'Paid', %s, %s)"
        cursor.execute(pay_query, (amount, payment_method, contract_id))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        st.error(f"Error processing payment: {err}")
        conn.rollback()
        return False

def db_get_my_reviews(conn, user_id):
    """Fetches all reviews for the logged-in user."""
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT fn_GetStudentAverageRating(%s) AS avg, fn_GetStudentReviewCount(%s) AS count", (user_id, user_id))
        stats = cursor.fetchone()
        
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
        
        return stats, reviews
    except mysql.connector.Error as err:
        st.error(f"Error fetching reviews: {err}")
        return None, []


# --- STREAMLIT UI PAGES ---

def show_login_page(conn):
    """Renders the Login and Sign Up pages."""
    
    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

    with login_tab:
        st.subheader("Login to PESUConnect")
        with st.form("login_form", clear_on_submit=True):
            email = st.text_input("Email (@pesu.edu)")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if not email or not password:
                    st.warning("Please fill in all fields.")
                else:
                    user = db_student_login(conn, email, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
    
    with signup_tab:
        st.subheader("Sign Up for PESUConnect")
        with st.form("signup_form"):
            email = st.text_input("Email (@pesu.edu)", key="reg_email")
            name = st.text_input("Full Name", key="reg_name")
            password = st.text_input("Password", type="password", key="reg_pass")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
            phone = st.text_input("Phone Number (optional)", key="reg_phone")
            department = st.text_input("Department (e.g., CSE)", key="reg_dept")
            year = st.number_input("Year of Study (e.g., 2)", min_value=1, max_value=8, step=1, key="reg_year")
            
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if not email or not name or not password or not department:
                    st.warning("Please fill in all required fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    success = db_student_register(conn, name, email, password, phone, department, year)
                    if success:
                        st.success("Registration successful! Please go to the Login tab.")
                    else:
                        st.error("Registration failed. Email may already be in use.")

def show_dashboard_page(conn):
    st.title(f"Welcome to your Dashboard, {st.session_state.user['name']}!")
    st.write("Use the sidebar to navigate the application.")
    
    st.subheader("Your Stats at a Glance")
    stats, reviews = db_get_my_reviews(conn, st.session_state.user['student_id'])
    
    if stats:
        col1, col2 = st.columns(2)
        col1.metric("Average Rating", f"{stats['avg']:.2f} / 5.00")
        col2.metric("Total Reviews", f"{stats['count']}")
    
    st.subheader("Your Active Projects")
    freelance_contracts, owner_contracts = db_get_my_contracts(conn, st.session_state.user['student_id'])
    
    st.write("**As Freelancer (Working on):**")
    if not freelance_contracts:
        st.write("You are not currently working on any projects.")
    else:
        for contract in freelance_contracts:
            st.write(f"- {contract['project_title']} (Owner: {contract['project_owner_name']})")
    
    st.write("**As Project Owner (Hired for):**")
    if not owner_contracts:
        st.write("You have not hired for any active projects.")
    else:
        for contract in owner_contracts:
            st.write(f"- {contract['project_title']} (Freelancer: {contract['freelancer_name']})")


def show_view_projects_page(conn):
    st.title("Available Projects")
    
    projects = db_get_open_projects(conn)
    
    if not projects:
        st.info("No open projects found.")
        return

    for proj in projects:
        with st.container(border=True):
            st.subheader(proj['title'])
            col1, col2 = st.columns(2)
            col1.write(f"**Owner:** {proj['owner_name']}")
            col2.write(f"**Deadline:** {proj['deadline'].strftime('%Y-%m-%d')}")
            st.write(f"**Description:** {proj['description']}")
            
            if st.button("Apply", key=f"apply_{proj['project_id']}"):
                success = db_apply_for_project(conn, st.session_state.user['student_id'], proj['project_id'])
                if success:
                    st.success(f"Successfully applied for '{proj['title']}'!")
                else:
                    st.error("Application failed. You may have already applied or this is your own project.")

def show_create_project_page(conn):
    st.title("Create a New Project")
    
    with st.form("create_project_form"):
        title = st.text_input("Project Title")
        description = st.text_area("Project Description")
        deadline = st.date_input("Deadline", min_value=datetime.date.today() + datetime.timedelta(days=1))
        
        submitted = st.form_submit_button("Post Project")
        
        if submitted:
            if not title or not description:
                st.warning("Please fill in all fields.")
            else:
                success = db_create_project(conn, st.session_state.user['student_id'], title, description, deadline)
                if success:
                    st.success("Your project has been posted!")
                else:
                    st.error("Error creating project.")

def show_manage_my_projects_page(conn):
    st.title("Manage My Projects")
    
    my_projects = db_get_my_projects(conn, st.session_state.user['student_id'])
    
    if not my_projects:
        st.info("You have not created any projects yet.")
        return
        
    for proj in my_projects:
        with st.expander(f"**{proj['title']}** ({proj['status']}) - {proj['pending_apps']} Pending"):
            st.write(f"**Project ID:** {proj['project_id']}")
            
            applications = db_get_pending_applications(conn, proj['project_id'])
            if not applications:
                st.write("No pending applications for this project.")
            else:
                st.write("**Pending Applications:**")
                for app in applications:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    col1.write(f"**Applicant:** {app['applicant_name']} (ID: {app['application_id']})")
                    
                    if col2.button("Accept", key=f"accept_{app['application_id']}"):
                        if db_accept_application(conn, app['application_id']):
                            st.success(f"Accepted {app['applicant_name']}! Contract created.")
                            st.rerun()
                        
                    if col3.button("Reject", key=f"reject_{app['application_id']}"):
                        if db_reject_application(conn, app['application_id']):
                            st.warning(f"Rejected {app['applicant_name']}.")
                            st.rerun()

def show_manage_skills_page(conn):
    st.title("Manage My Skills")
    
    st.subheader("Your Current Skills")
    my_skills = db_get_my_skills(conn, st.session_state.user['student_id'])
    if not my_skills:
        st.info("You have not added any skills yet.")
    else:
        for skill in my_skills:
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.write(f"**{skill['skill_name']}** (ID: {skill['skill_id']})")
            col2.write(f"Level: {skill['proficiency_level']}")
            
            with col3.popover("Update"):
                with st.form(f"update_skill_{skill['skill_id']}"):
                    new_level = st.selectbox("New Proficiency", ["Beginner", "Intermediate", "Advanced"], index=["Beginner", "Intermediate", "Advanced"].index(skill['proficiency_level']), key=f"level_{skill['skill_id']}")
                    if st.form_submit_button("Update"):
                        if db_update_skill(conn, st.session_state.user['student_id'], skill['skill_id'], new_level):
                            st.success("Skill updated!")
                            st.rerun()
            
            if col4.button("Remove", key=f"remove_skill_{skill['skill_id']}"):
                if db_remove_skill(conn, st.session_state.user['student_id'], skill['skill_id']):
                    st.success("Skill removed!")
                    st.rerun()

    st.subheader("Add a New Skill")
    with st.form("add_skill_form"):
        skill_name = st.text_input("Skill Name (e.g., Python)")
        proficiency = st.selectbox("Proficiency", ["Beginner", "Intermediate", "Advanced"])
        if st.form_submit_button("Add Skill"):
            if not skill_name:
                st.warning("Please enter a skill name.")
            else:
                if db_add_skill(conn, st.session_state.user['student_id'], skill_name, proficiency):
                    st.success(f"'{skill_name}' added to your profile!")
                    st.rerun()

def show_active_contracts_page(conn):
    st.title("Your Active Contracts")
    
    freelance_contracts, owner_contracts = db_get_my_contracts(conn, st.session_state.user['student_id'])

    st.subheader("Contracts as Freelancer (Working on)")
    if not freelance_contracts:
        st.info("You are not currently working on any projects.")
    else:
        for contract in freelance_contracts:
            with st.container(border=True):
                st.write(f"**Project:** {contract['project_title']}")
                st.write(f"**Owner:** {contract['project_owner_name']}")
                st.write(f"**Dates:** {contract['start_date']} to {contract['end_date']}")

    st.subheader("Contracts as Project Owner (Hired for)")
    if not owner_contracts:
        st.info("You have not hired for any active projects.")
    else:
        st.write("You can complete a contract here, which will allow you to leave a review and process payment.")
        for contract in owner_contracts:
            with st.container(border=True):
                st.write(f"**Project:** {contract['project_title']}")
                st.write(f"**Freelancer:** {contract['freelancer_name']}")
                st.write(f"**Contract ID:** {contract['contract_id']}")
                st.write(f"**Dates:** {contract['start_date']} to {contract['end_date']}")
                
                if st.button("Complete Contract", key=f"complete_{contract['contract_id']}"):
                    # Use session state to open the review/payment modal
                    st.session_state.contract_to_complete = contract
    
    # --- Completion "Modal" ---
    if 'contract_to_complete' in st.session_state:
        contract = st.session_state.contract_to_complete
        with st.form(f"complete_form_{contract['contract_id']}"):
            st.subheader(f"Complete: {contract['project_title']}")
            st.write(f"You are about to complete the contract with {contract['freelancer_name']}.")
            
            st.write("Please leave a review:")
            rating = st.slider("Rating (1-5)", 1, 5, 5)
            review_text = st.text_area("Review Comment")
            
            st.write("Please process payment:")
            amount = st.number_input("Payment Amount", min_value=0.01, step=10.0)
            payment_method = st.selectbox("Payment Method", ["UPI", "Card", "Bank Transfer"])
            
            submitted = st.form_submit_button("Submit Completion")
            
            if submitted:
                if not review_text or not amount:
                    st.warning("Please fill in all review and payment fields.")
                else:
                    # This is a 3-step transaction
                    if db_complete_contract(conn, contract['contract_id']):
                        if db_create_review(conn, review_text, rating, contract['contract_id'], st.session_state.user['student_id']):
                            if db_create_payment(conn, amount, payment_method, contract['contract_id']):
                                st.success("Contract completed, review submitted, and payment processed!")
                                del st.session_state.contract_to_complete
                                st.rerun()
                            else:
                                st.error("Payment failed. Please try again.")
                        else:
                            st.error("Review failed. Please try again.")
                    else:
                        st.error("Contract completion failed. Please try again.")

def show_my_reviews_page(conn):
    st.title("My Reviews")
    
    stats, reviews = db_get_my_reviews(conn, st.session_state.user['student_id'])
    
    if stats:
        st.metric("Your Average Rating", f"{stats['avg']:.2f} / 5.00", f"{stats['count']} Total Reviews")
    else:
        st.info("You have 0 reviews.")

    st.divider()
    
    if not reviews:
        st.info("No review comments found.")
    else:
        st.subheader("All Comments")
        for review in reviews:
            with st.container(border=True):
                st.write(f"**Project:** {review['project_title']}")
                st.write(f"**Rating:** {'⭐' * review['rating']} ({review['rating']}/5)")
                st.write(f"**Comment:** {review['review_text']}")


# --- MAIN APPLICATION ---

def main():
    st.set_page_config(page_title="PESUConnect", layout="centered")

    # Initialize session state variables
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None

    # Get DB connection
    conn = connect_to_db()
    if not conn:
        st.error("Failed to connect to the database. Please check your .env file and database server.")
        return

    # --- MAIN ROUTING ---
    if not st.session_state.logged_in:
        st.title("Welcome to PESUConnect")
        show_login_page(conn)
    else:
        # --- Logged-in View: Sidebar Navigation ---
        st.sidebar.title(f"Welcome, {st.session_state.user['name']}!")
        st.sidebar.caption(f"ID: {st.session_state.user['student_id']}")
        
        page_options = [
            "Dashboard", 
            "View Available Projects", 
            "Create a New Project", 
            "Manage My Projects", 
            "Manage My Skills",
            "View Active Contracts",
            "View My Reviews"
        ]
        page = st.sidebar.radio("Navigation", page_options)
        
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()

        # --- Page Content ---
        if page == "Dashboard":
            show_dashboard_page(conn)
        elif page == "View Available Projects":
            show_view_projects_page(conn)
        elif page == "Create a New Project":
            show_create_project_page(conn)
        elif page == "Manage My Projects":
            show_manage_my_projects_page(conn)
        elif page == "Manage My Skills":
            show_manage_skills_page(conn)
        elif page == "View Active Contracts":
            show_active_contracts_page(conn)
        elif page == "View My Reviews":
            show_my_reviews_page(conn)
            
if __name__ == "__main__":
    main()
