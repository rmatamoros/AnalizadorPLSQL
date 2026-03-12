-- Bad PL/SQL example - intentionally violates many standards
-- Used to demonstrate the analyzer's detection capabilities

CREATE OR REPLACE PACKAGE BODY employee_pkg AS

  PROCEDURE updateSalary(employee_id NUMBER, new_salary NUMBER) AS
    empName VARCHAR2(100);
    empCount NUMBER;
    status VARCHAR2(20);
  BEGIN
    -- Get employee count
    SELECT COUNT(*) INTO empCount FROM employees;

    -- Get all employee data
    SELECT * INTO empName FROM employees WHERE id = employee_id;

    IF empCount > 1000 THEN
      UPDATE employees SET salary = new_salary WHERE id = employee_id;
      COMMIT;
    END IF;

    -- Loop with commit (bad practice)
    FOR i IN 1..empCount LOOP
      UPDATE audit_log SET processed = 'Y' WHERE emp_id = i;
      COMMIT;
    END LOOP;

  EXCEPTION
    WHEN OTHERS THEN
      NULL;
  END updateSalary;

  FUNCTION getEmployeeBonus(empId NUMBER) RETURN NUMBER AS
    bonus NUMBER;
    multiplier NUMBER := 2.5;
  BEGIN
    -- Dynamic SQL with concatenation (SQL injection risk)
    EXECUTE IMMEDIATE 'SELECT bonus FROM bonuses WHERE id = ' || empId INTO bonus;

    RETURN bonus * multiplier;
  END getEmployeeBonus;

  PROCEDURE fetchAllEmployees AS
    CURSOR emp_cursor IS SELECT * FROM employees;
    emp_record emp_cursor%ROWTYPE;
  BEGIN
    OPEN emp_cursor;
    LOOP
      FETCH emp_cursor INTO emp_record;
      EXIT WHEN emp_cursor%NOTFOUND;
      -- Process row by row (should use BULK COLLECT)
      INSERT INTO emp_archive VALUES emp_record;
    END LOOP;
    CLOSE emp_cursor;

    COMMIT;
  END fetchAllEmployees;

  PROCEDURE authenticateUser(username VARCHAR2, password VARCHAR2) AS
    stored_pwd VARCHAR2(50);
    hardcoded_secret CONSTANT VARCHAR2(20) := 'mySecretKey123';
  BEGIN
    SELECT pwd INTO stored_pwd FROM users WHERE uname = username;

    IF stored_pwd = password THEN
      DBMS_OUTPUT.PUT_LINE('Password: ' || password);
      DBMS_OUTPUT.PUT_LINE('Login successful for: ' || username);
    END IF;

  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      NULL;
  END authenticateUser;

END employee_pkg;
/
