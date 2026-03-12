-- =============================================================================
-- Package: pkg_employee_mgmt
-- Author:  Juan Perez
-- Date:    2024-01-15
-- Description: Employee management package with salary updates,
--              bonus calculations, and archive processing.
--              Follows Oracle PL/SQL corporate coding standards.
-- =============================================================================

CREATE OR REPLACE PACKAGE pkg_employee_mgmt AS

  -- Public exceptions
  e_invalid_salary  EXCEPTION;
  e_employee_not_found EXCEPTION;

  -- Public constants
  c_max_salary     CONSTANT NUMBER := 999999;
  c_min_salary     CONSTANT NUMBER := 1000;
  c_bulk_limit     CONSTANT PLS_INTEGER := 100;

  -- ==========================================================================
  -- Procedure: update_salary
  -- Author:    Juan Perez
  -- Date:      2024-01-15
  -- Description: Updates the salary for a given employee, applying
  --              validation rules and logging the change.
  -- Parameters:
  --   p_employee_id  IN  - Employee identifier
  --   p_new_salary   IN  - New salary amount (must be between c_min_salary and c_max_salary)
  -- ==========================================================================
  PROCEDURE update_salary(
    p_employee_id IN employees.employee_id%TYPE,
    p_new_salary  IN employees.salary%TYPE
  );

  -- ==========================================================================
  -- Function: get_employee_bonus
  -- Author:   Juan Perez
  -- Date:     2024-01-15
  -- Description: Calculates the annual bonus for an employee based on
  --              performance rating and department budget.
  -- Parameters:
  --   p_employee_id  IN  - Employee identifier
  -- Returns: Calculated bonus amount as NUMBER
  -- ==========================================================================
  FUNCTION get_employee_bonus(
    p_employee_id IN employees.employee_id%TYPE
  ) RETURN NUMBER;

  -- ==========================================================================
  -- Procedure: archive_terminated_employees
  -- Author:    Juan Perez
  -- Date:      2024-01-15
  -- Description: Archives all terminated employees using bulk operations
  --              for optimal performance.
  -- ==========================================================================
  PROCEDURE archive_terminated_employees;

END pkg_employee_mgmt;
/

CREATE OR REPLACE PACKAGE BODY pkg_employee_mgmt AS

  -- ==========================================================================
  -- Procedure: update_salary
  -- ==========================================================================
  PROCEDURE update_salary(
    p_employee_id IN employees.employee_id%TYPE,
    p_new_salary  IN employees.salary%TYPE
  ) AS
    v_current_salary  employees.salary%TYPE;
    v_employee_name   employees.full_name%TYPE;
    v_dept_id         employees.department_id%TYPE;
  BEGIN
    -- Validate salary range
    IF p_new_salary < c_min_salary OR p_new_salary > c_max_salary THEN
      RAISE e_invalid_salary;
    END IF;

    -- Fetch current employee data (specific columns, no SELECT *)
    SELECT e.salary, e.full_name, e.department_id
      INTO v_current_salary, v_employee_name, v_dept_id
      FROM employees e
     WHERE e.employee_id = p_employee_id;

    -- Perform the update
    UPDATE employees
       SET salary     = p_new_salary,
           updated_at = SYSDATE,
           updated_by = SYS_CONTEXT('USERENV', 'SESSION_USER')
     WHERE employee_id = p_employee_id;

    -- Log the salary change
    INSERT INTO salary_audit_log (
      employee_id, old_salary, new_salary, changed_by, changed_at
    ) VALUES (
      p_employee_id, v_current_salary, p_new_salary,
      SYS_CONTEXT('USERENV', 'SESSION_USER'), SYSDATE
    );

  EXCEPTION
    WHEN e_invalid_salary THEN
      RAISE_APPLICATION_ERROR(
        -20001,
        'Invalid salary: ' || p_new_salary ||
        '. Must be between ' || c_min_salary || ' and ' || c_max_salary
      );
    WHEN NO_DATA_FOUND THEN
      RAISE e_employee_not_found;
    WHEN OTHERS THEN
      -- Log unexpected errors before re-raising
      INSERT INTO error_log (error_code, error_msg, procedure_name, created_at)
      VALUES (SQLCODE, SQLERRM, 'pkg_employee_mgmt.update_salary', SYSDATE);
      COMMIT; -- Commit the error log entry (autonomous or top-level)
      RAISE;
  END update_salary;

  -- ==========================================================================
  -- Function: get_employee_bonus
  -- ==========================================================================
  FUNCTION get_employee_bonus(
    p_employee_id IN employees.employee_id%TYPE
  ) RETURN NUMBER AS
    v_bonus           NUMBER;
    v_performance     performance_reviews.rating%TYPE;
    v_dept_budget     departments.bonus_budget%TYPE;
    c_base_multiplier CONSTANT NUMBER := 0.1;
  BEGIN
    -- Get performance rating and department budget
    SELECT pr.rating, d.bonus_budget
      INTO v_performance, v_dept_budget
      FROM performance_reviews pr
      JOIN employees e       ON e.employee_id = pr.employee_id
      JOIN departments d     ON d.department_id = e.department_id
     WHERE pr.employee_id = p_employee_id
       AND pr.review_year = EXTRACT(YEAR FROM SYSDATE);

    -- Calculate bonus: base_multiplier * performance_rating * dept_budget
    v_bonus := c_base_multiplier * v_performance * v_dept_budget;

    RETURN v_bonus;

  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      -- No review found for this year — return zero bonus
      RETURN 0;
    WHEN OTHERS THEN
      INSERT INTO error_log (error_code, error_msg, procedure_name, created_at)
      VALUES (SQLCODE, SQLERRM, 'pkg_employee_mgmt.get_employee_bonus', SYSDATE);
      RAISE;
  END get_employee_bonus;

  -- ==========================================================================
  -- Procedure: archive_terminated_employees
  -- ==========================================================================
  PROCEDURE archive_terminated_employees AS
    -- Bulk collection types
    TYPE t_employee_ids   IS TABLE OF employees.employee_id%TYPE INDEX BY PLS_INTEGER;
    TYPE t_employee_recs  IS TABLE OF employees%ROWTYPE           INDEX BY PLS_INTEGER;

    v_emp_ids   t_employee_ids;
    v_emp_recs  t_employee_recs;
    v_count     PLS_INTEGER := 0;

    -- Cursor for terminated employees (specific columns, not SELECT *)
    CURSOR cur_terminated IS
      SELECT employee_id, full_name, department_id, salary,
             hire_date, termination_date, status
        FROM employees
       WHERE status = 'TERMINATED'
         AND termination_date < SYSDATE - 90; -- Older than 90 days
  BEGIN
    -- Use BULK COLLECT with LIMIT for memory-efficient processing
    OPEN cur_terminated;
    LOOP
      FETCH cur_terminated BULK COLLECT INTO v_emp_recs LIMIT c_bulk_limit;
      EXIT WHEN v_emp_recs.COUNT = 0;

      -- Bulk insert into archive
      FORALL i IN 1..v_emp_recs.COUNT
        INSERT INTO employees_archive
        VALUES v_emp_recs(i);

      -- Collect IDs for bulk delete
      FOR i IN 1..v_emp_recs.COUNT LOOP
        v_emp_ids(i) := v_emp_recs(i).employee_id;
      END LOOP;

      -- Bulk delete from main table
      FORALL i IN 1..v_emp_ids.COUNT
        DELETE FROM employees WHERE employee_id = v_emp_ids(i);

      v_count := v_count + v_emp_recs.COUNT;
    END LOOP;
    CLOSE cur_terminated;

    DBMS_OUTPUT.PUT_LINE('Archived ' || v_count || ' terminated employees.');

  EXCEPTION
    WHEN OTHERS THEN
      IF cur_terminated%ISOPEN THEN
        CLOSE cur_terminated;
      END IF;
      INSERT INTO error_log (error_code, error_msg, procedure_name, created_at)
      VALUES (SQLCODE, SQLERRM, 'pkg_employee_mgmt.archive_terminated_employees', SYSDATE);
      RAISE;
  END archive_terminated_employees;

END pkg_employee_mgmt;
/
