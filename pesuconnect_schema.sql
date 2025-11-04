CREATE DATABASE IF NOT EXISTS pesuConnect;
USE pesuConnect;

CREATE TABLE Student (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(50) NOT NULL, -- SHA1 is 40 chars
    phone_number VARCHAR(15),
    department VARCHAR(50),
    year_of_study INT
);

CREATE TABLE Project (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    post_date DATE,
    deadline DATE,
    status VARCHAR(20) DEFAULT 'Open',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE SET NULL
);

CREATE TABLE Application (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    application_date DATE,
    status VARCHAR(20) DEFAULT 'Pending',
    student_id INT,
    project_id INT,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES Project(project_id) ON DELETE CASCADE
);

CREATE TABLE Contract (
    contract_id INT AUTO_INCREMENT PRIMARY KEY,
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'In Progress',
    student_id INT,
    project_id INT,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES Project(project_id) ON DELETE CASCADE
);

CREATE TABLE Payment (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    amount DECIMAL(10, 2) NOT NULL,
    payment_date DATE,
    status VARCHAR(20) DEFAULT 'Pending',
    payment_method VARCHAR(50),
    contract_id INT,
    FOREIGN KEY (contract_id) REFERENCES Contract(contract_id) ON DELETE SET NULL
);

CREATE TABLE Review (
    review_id INT AUTO_INCREMENT PRIMARY KEY,
    review_text TEXT,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    student_id INT, -- The student being reviewed
    contract_id INT,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES Contract(contract_id) ON DELETE SET NULL
);

CREATE TABLE Skill (
    skill_id INT AUTO_INCREMENT PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE,
    skill_description TEXT
);

CREATE TABLE Student_Skill (
    student_id INT,
    skill_id INT,
    proficiency_level ENUM('Beginner', 'Intermediate', 'Advanced'),
    PRIMARY KEY (student_id, skill_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES Skill(skill_id) ON DELETE CASCADE
);

DELIMITER //

CREATE TRIGGER trg_Validate_PESU_Email
BEFORE INSERT ON Student
FOR EACH ROW
BEGIN
    IF NOT NEW.email LIKE '%@pesu.edu' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Registration is limited to @pesu.edu email addresses.';
    END IF;
END //

CREATE TRIGGER trg_Hash_Student_Password_INSERT
BEFORE INSERT ON Student
FOR EACH ROW
BEGIN
    SET NEW.password = SHA1(NEW.password);
END //

CREATE TRIGGER trg_Hash_Student_Password_UPDATE
BEFORE UPDATE ON Student
FOR EACH ROW
BEGIN
    IF NEW.password != OLD.password THEN
        SET NEW.password = SHA1(NEW.password);
    END IF;
END //

CREATE TRIGGER trg_Validate_Project_Deadline_INSERT
BEFORE INSERT ON Project
FOR EACH ROW
BEGIN
    IF NEW.deadline <= CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Project deadline must be in the future.';
    END IF;
    -- Set post_date on insert
    SET NEW.post_date = CURDATE();
END //

CREATE TRIGGER trg_Validate_Project_Deadline_UPDATE
BEFORE UPDATE ON Project
FOR EACH ROW
BEGIN
    IF NEW.deadline <= CURDATE() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Project deadline must be in the future.';
    END IF;
END //

CREATE TRIGGER trg_Prevent_Self_Application
BEFORE INSERT ON Application
FOR EACH ROW
BEGIN
    DECLARE v_project_owner_id INT;
    SELECT student_id INTO v_project_owner_id FROM Project WHERE project_id = NEW.project_id;
    IF v_project_owner_id = NEW.student_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: A student cannot apply to their own project.';
    END IF;
END //

CREATE TRIGGER trg_Check_Project_Status_On_Apply
BEFORE INSERT ON Application
FOR EACH ROW
BEGIN
    DECLARE v_project_status VARCHAR(20);
    SELECT status INTO v_project_status FROM Project WHERE project_id = NEW.project_id;
    IF v_project_status != 'Open' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: This project is no longer open for applications.';
    END IF;
END //

CREATE TRIGGER trg_Prevent_Duplicate_Application
BEFORE INSERT ON Application
FOR EACH ROW
BEGIN
    DECLARE v_application_count INT;
    SELECT COUNT(*) INTO v_application_count FROM Application
    WHERE student_id = NEW.student_id AND project_id = NEW.project_id;
    IF v_application_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: You have already applied to this project.';
    END IF;
END //

CREATE TRIGGER trg_Validate_Skill_Proficiency_INSERT
BEFORE INSERT ON Student_Skill
FOR EACH ROW
BEGIN
    IF NEW.proficiency_level NOT IN ('Beginner', 'Intermediate', 'Advanced') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Proficiency must be Beginner, Intermediate, or Advanced.';
    END IF;
END //

CREATE TRIGGER trg_Validate_Skill_Proficiency_UPDATE
BEFORE UPDATE ON Student_Skill
FOR EACH ROW
BEGIN
    IF NEW.proficiency_level NOT IN ('Beginner', 'Intermediate', 'Advanced') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Proficiency must be Beginner, Intermediate, or Advanced.';
    END IF;
END //

CREATE TRIGGER trg_Validate_Payment_Amount
BEFORE INSERT ON Payment
FOR EACH ROW
BEGIN
    IF NEW.amount <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Payment amount must be greater than zero.';
    END IF;
END //

-- Purpose: Securely logs in a student.
CREATE PROCEDURE sp_StudentLogin(
    IN in_email VARCHAR(100),
    IN in_password VARCHAR(100)
)
BEGIN
    DECLARE v_hashed_password VARCHAR(50);
    SET v_hashed_password = SHA1(in_password);
    
    SELECT 
        student_id, 
        name, 
        email,
        phone_number,
        department,
        year_of_study
    FROM Student
    WHERE 
        email = in_email AND password = v_hashed_password;
END //

-- Purpose: Creates a new project.
CREATE PROCEDURE sp_CreateProject(
    IN in_student_id INT,
    IN in_title VARCHAR(100),
    IN in_description TEXT,
    IN in_deadline DATE
)
BEGIN
    INSERT INTO Project (student_id, title, description, deadline, status)
    VALUES (in_student_id, in_title, in_description, in_deadline, 'Open');
    
    SELECT LAST_INSERT_ID() AS new_project_id;
END //

-- Purpose: Searches for projects.
CREATE PROCEDURE sp_SearchProjects(
    IN in_keyword VARCHAR(100),
    IN in_status VARCHAR(20)
)
BEGIN
    DECLARE v_keyword VARCHAR(102);
    SET v_keyword = CONCAT('%', in_keyword, '%');
    
    SELECT 
        p.project_id, 
        p.title, 
        p.description, 
        p.deadline, 
        p.status,
        s.name AS owner_name
    FROM Project p
    LEFT JOIN Student s ON p.student_id = s.student_id
    WHERE 
        -- FIX: Skips LIKE check if keyword is NULL
        (in_keyword IS NULL OR p.title LIKE v_keyword OR p.description LIKE v_keyword)
        AND (in_status IS NULL OR p.status = in_status);
END //

-- Purpose: Allows a student to apply for a project.
CREATE PROCEDURE sp_CreateApplication(
    IN in_student_id INT,
    IN in_project_id INT
)
BEGIN
    INSERT INTO Application (application_date, student_id, project_id)
    VALUES (CURDATE(), in_student_id, in_project_id);
END //

-- Purpose: Accepts an application, creates a contract, and updates statuses.
CREATE PROCEDURE sp_AcceptApplication(
    IN in_application_id INT
)
BEGIN
    DECLARE v_student_id INT;
    DECLARE v_project_id INT;
    DECLARE v_project_deadline DATE;

    SELECT student_id, project_id
    INTO v_student_id, v_project_id
    FROM Application
    WHERE application_id = in_application_id AND status = 'Pending';

    SELECT deadline
    INTO v_project_deadline
    FROM Project
    WHERE project_id = v_project_id;

    IF v_student_id IS NOT NULL THEN
        START TRANSACTION;
        
        UPDATE Application
        SET status = 'Accepted'
        WHERE application_id = in_application_id;
        
        INSERT INTO Contract (start_date, end_date, student_id, project_id)
        VALUES (CURDATE(), v_project_deadline, v_student_id, v_project_id);
        
        UPDATE Project
        SET status = 'In Progress'
        WHERE project_id = v_project_id;
        
        UPDATE Application
        SET status = 'Rejected'
        WHERE project_id = v_project_id AND status = 'Pending';
        
        COMMIT;
    END IF;
END //

-- Purpose: Rejects a single application.
CREATE PROCEDURE sp_RejectApplication(IN in_application_id INT)
BEGIN
    UPDATE Application
    SET status = 'Rejected'
    WHERE application_id = in_application_id AND status = 'Pending';
END //

-- Purpose: Marks a contract/project as 'Completed'.
CREATE PROCEDURE sp_CompleteContract(
    IN in_contract_id INT
)
BEGIN
    DECLARE v_project_id INT;
    
    SELECT project_id 
    INTO v_project_id
    FROM Contract 
    WHERE contract_id = in_contract_id;
    
    IF v_project_id IS NOT NULL THEN
        START TRANSACTION;
        
        UPDATE Contract
        SET status = 'Completed', end_date = CURDATE()
        WHERE contract_id = in_contract_id;
        
        UPDATE Project
        SET status = 'Completed'
        WHERE project_id = v_project_id;
        
        COMMIT;
    END IF;
END //

-- Purpose: Allows a project owner to review a student after a contract.
CREATE PROCEDURE sp_CreateReview(
    IN in_review_text TEXT,
    IN in_rating INT,
    IN in_contract_id INT,
    IN in_reviewer_student_id INT
)
BEGIN
    DECLARE v_freelancer_student_id INT;
    DECLARE v_project_owner_id INT;
    
    -- Get the student_id (freelancer) and project_owner_id from the contract/project
    SELECT c.student_id, p.student_id
    INTO v_freelancer_student_id, v_project_owner_id
    FROM Contract c
    JOIN Project p ON c.project_id = p.project_id
    WHERE c.contract_id = in_contract_id;
    
    -- Ensure the person writing the review is the project owner
    IF v_project_owner_id = in_reviewer_student_id THEN
        -- Insert the review for the FREELANCER
        INSERT INTO Review (review_text, rating, contract_id, student_id)
        VALUES (in_review_text, in_rating, in_contract_id, v_freelancer_student_id);
    ELSE
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Only the project owner can leave a review.';
    END IF;
END //

CREATE FUNCTION fn_GetStudentAverageRating(in_student_id INT)
RETURNS DECIMAL(3, 2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_avg_rating DECIMAL(3, 2);
    SELECT AVG(rating) INTO v_avg_rating FROM Review WHERE student_id = in_student_id;
    IF v_avg_rating IS NULL THEN
        SET v_avg_rating = 0.00;
    END IF;
    RETURN v_avg_rating;
END //

CREATE FUNCTION fn_GetStudentReviewCount(in_student_id INT)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_review_count INT;
    SELECT COUNT(*) INTO v_review_count FROM Review WHERE student_id = in_student_id;
    RETURN v_review_count;
END //

CREATE FUNCTION fn_GetProjectApplicationCount(in_project_id INT)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_app_count INT;
    SELECT COUNT(*) INTO v_app_count FROM Application
    WHERE project_id = in_project_id AND status = 'Pending';
    RETURN v_app_count;
END //

DELIMITER ;
