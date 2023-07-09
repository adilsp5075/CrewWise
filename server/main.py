from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date
from database import connect_to_db
    
app = FastAPI()

origins=["*"]

# Add the CORS middleware to the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    app.state.connection_pool = await connect_to_db()

@app.on_event("shutdown")
async def shutdown():
    await app.state.connection_pool.close()



class Employee(BaseModel):
    name: str
    email: str
    contact_number: str
    date_of_joining: date
    years_of_experience: int

class Department(BaseModel):
    name: str
    location: str
    manager_id: int

class EmployeeDepartmentAssignment(BaseModel):
    employee_id: int
    department_id: int


class EmployeePromotion(BaseModel):
    employee_id: int


'''-----------------------Employees---------------------------------'''

@app.post("/employees")
async def create_employee(employee: Employee):
    async with app.state.connection_pool.acquire() as connection:
        query = """
            INSERT INTO Employee (name, email, contact_number, date_of_joining, years_of_experience)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING employee_id, name, email, contact_number, date_of_joining, years_of_experience
        """
        values = (
            employee.name,
            employee.email,
            employee.contact_number,
            employee.date_of_joining,
            employee.years_of_experience,
        )
        created_employee = await connection.fetchrow(query, *values)
        return created_employee


@app.get("/employees/{employee_id}")
async def get_employee(employee_id: int):
    async with app.state.connection_pool.acquire() as connection:
        query = "SELECT * FROM Employee WHERE employee_id = $1"
        employee = await connection.fetchrow(query, employee_id)
        if employee:
            return employee
        else:
            return {"error": "Employee not found"}
        
@app.get("/employees")
async def get_all_employees():
    async with app.state.connection_pool.acquire() as connection:
        query = "SELECT * FROM Employee"
        employees = await connection.fetch(query)
        return employees


# Endpoint to update an employee by ID
@app.put("/employees/{employee_id}")
async def update_employee(employee_id: int, employee: Employee):
    async with app.state.connection_pool.acquire() as connection:
        query = """
            UPDATE Employee
            SET name = $2, email = $3, contact_number = $4, date_of_joining = $5, years_of_experience = $6
            WHERE employee_id = $1
        """
        values = (
            employee_id,
            employee.name,
            employee.email,
            employee.contact_number,
            employee.date_of_joining,
            employee.years_of_experience,
        )
        result = await connection.execute(query, *values)
        if result == "UPDATE 1":
            return {"message": "Employee updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Employee not found")

# Endpoint to delete an employee by ID
@app.delete("/employees/{employee_id}")
async def delete_employee(employee_id: int):
    async with app.state.connection_pool.acquire() as connection:
        query = """
            DELETE FROM Employee WHERE employee_id = $1
        """
        result = await connection.execute(query, employee_id)
        if result == "DELETE 1":
            return {"message": "Employee deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Employee not found")
        

'''-----------------------Departments---------------------------------'''


# Create a new department
@app.post("/departments")
async def create_department(department: Department):
    async with app.state.connection_pool.acquire() as connection:
        # Check if the manager employee exists and has experience over 5 years
        manager_query = "SELECT * FROM Employee WHERE employee_id = $1"
        manager = await connection.fetchrow(manager_query, department.manager_id)
        if not manager:
            raise HTTPException(status_code=400, detail="Invalid manager for the department. Manager not found.")

        date_of_joining = manager['date_of_joining']
        years_of_experience = (date.today() - date_of_joining).days // 365
        if years_of_experience < 5:
            raise HTTPException(status_code=400, detail="Manager does not meet experience criteria for the department. Manager must have at least 5 years of experience.")

        # Create the department
        query = """
            INSERT INTO Department (name, location, manager_id)
            VALUES ($1, $2, $3)
            RETURNING department_id, name, location, manager_id
        """
        values = (
            department.name,
            department.location,
            department.manager_id,
        )
        created_department = await connection.fetchrow(query, *values)
        return created_department

# Get department by ID
@app.get("/departments/{department_id}")
async def get_department(department_id: int):
    async with app.state.connection_pool.acquire() as connection:
        query = """
            SELECT d.department_id, d.name, d.location, e.name AS manager_name, e.email AS manager_email, e.contact_number AS manager_contact_number
            FROM Department d
            INNER JOIN Employee e ON d.manager_id = e.employee_id
            WHERE d.department_id = $1
        """
        department = await connection.fetchrow(query, department_id)
        if department:
            return department
        else:
            return {"error": "Department not found"}

# Get all departments
@app.get("/departments")
async def get_all_departments():
    async with app.state.connection_pool.acquire() as connection:
        query = """
            SELECT d.department_id, d.name, d.location, e.name AS manager_name, e.email AS manager_email, e.contact_number AS manager_contact_number
            FROM Department d
            INNER JOIN Employee e ON d.manager_id = e.employee_id
        """
        departments = await connection.fetch(query)
        return departments

# Update department by ID
@app.put("/departments/{department_id}")
async def update_department(department_id: int, department: Department):
    async with app.state.connection_pool.acquire() as connection:
        # Check if the department exists
        department_query = "SELECT * FROM Department WHERE department_id = $1"
        existing_department = await connection.fetchrow(department_query, department_id)
        if not existing_department:
            raise HTTPException(status_code=404, detail="Department not found")

        # Get the current manager details
        current_manager_query = """
            SELECT e.name AS manager_name, e.email AS manager_email, e.contact_number AS manager_contact_number
            FROM Employee e
            WHERE e.employee_id = $1
        """
        current_manager = await connection.fetchrow(current_manager_query, existing_department["manager_id"])

        # If the manager ID is being updated
        if department.manager_id != existing_department["manager_id"]:
            # Check if the new manager exists
            new_manager_query = """
                SELECT e.name AS manager_name, e.email AS manager_email, e.contact_number AS manager_contact_number
                FROM Employee e
                WHERE e.employee_id = $1
            """
            new_manager = await connection.fetchrow(new_manager_query, department.manager_id)
            if not new_manager:
                raise HTTPException(status_code=400, detail="Invalid manager. Manager not found.")

            # Check if the new manager has the necessary experience
            date_of_joining = new_manager["date_of_joining"]
            years_of_experience = (date.today() - date_of_joining).days // 365
            if years_of_experience < 5:
                raise HTTPException(status_code=400, detail="Invalid manager. Manager does not meet experience criteria.")

        query = """
            UPDATE Department
            SET name = $2, location = $3, manager_id = $4
            WHERE department_id = $1
        """
        values = (
            department_id,
            department.name,
            department.location,
            department.manager_id,
        )
        result = await connection.execute(query, *values)
        if result == "UPDATE 1":
            # Fetch the updated department with the new manager details
            updated_department_query = """
                SELECT d.department_id, d.name, d.location, e.name AS manager_name, e.email AS manager_email, e.contact_number AS manager_contact_number
                FROM Department d
                INNER JOIN Employee e ON d.manager_id = e.employee_id
                WHERE d.department_id = $1
            """
            updated_department = await connection.fetchrow(updated_department_query, department_id)
            return updated_department
        else:
            raise HTTPException(status_code=404, detail="Department not found")


# Delete department by ID
@app.delete("/departments/{department_id}")
async def delete_department(department_id: int):
    async with app.state.connection_pool.acquire() as connection:
        query = """
            DELETE FROM Department WHERE department_id = $1
        """
        result = await connection.execute(query, department_id)
        if result == "DELETE 1":
            return {"message": "Department deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Department not found")



@app.get("/departments")
async def get_all_departments():
    async with app.state.connection_pool.acquire() as connection:
        query = "SELECT * FROM Department"
        departments = await connection.fetch(query)
        return departments
    

# Get names of eligible managers
@app.get("/managers")
async def get_eligible_managers():
    async with app.state.connection_pool.acquire() as connection:
        query = """
            SELECT name, date_of_joining
            FROM Employee
        """
        employees = await connection.fetch(query)

        eligible_managers = []
        today = date.today()

        for employee in employees:
            date_of_joining = employee["date_of_joining"]
            years_of_experience = (today - date_of_joining).days // 365

            if years_of_experience >= 5:
                eligible_managers.append(employee["name"])

        return eligible_managers

'''-----------------------EmployeeDepartmentAssignment---------------------------------'''

@app.put("/employees/{employee_id}/assign_department/{department_id}")
async def assign_employee_department(employee_id: int, department_id: int):
    async with app.state.connection_pool.acquire() as connection:
        # Check if the employee exists
        employee_query = "SELECT * FROM Employee WHERE employee_id = $1"
        employee = await connection.fetchrow(employee_query, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check if the department exists
        department_query = "SELECT * FROM Department WHERE department_id = $1"
        department = await connection.fetchrow(department_query, department_id)
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")

        # Check if the employee is already assigned to a department
        existing_assignment_query = "SELECT * FROM Employee_Department_Assignment WHERE employee_id = $1"
        existing_assignment = await connection.fetchrow(existing_assignment_query, employee_id)
        if existing_assignment:
            raise HTTPException(status_code=400, detail="Employee is already assigned to a department")

        # Assign the employee to the department
        assignment_query = """
            INSERT INTO Employee_Department_Assignment (employee_id, department_id)
            VALUES ($1, $2)
            RETURNING employee_id, department_id
        """
        assignment_values = (employee_id, department_id)
        assigned_employee_department = await connection.fetchrow(assignment_query, *assignment_values)
        return assigned_employee_department

@app.put("/employees/{employee_id}/promote")
async def promote_employee(employee_id: int):
    async with app.state.connection_pool.acquire() as connection:
        # Check if the employee exists
        employee_query = "SELECT * FROM Employee WHERE employee_id = $1"
        employee = await connection.fetchrow(employee_query, employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Calculate the employee's years of experience
        date_of_joining = employee['date_of_joining']
        years_of_experience = (date.today() - date_of_joining).days // 365

        # Check if the employee meets the promotion criteria
        if years_of_experience < 5:
            raise HTTPException(status_code=400, detail="Employee does not meet experience criteria for promotion")

        # Update the employee's role to manager
        update_query = """
            UPDATE Employee
            SET role = 'manager'
            WHERE employee_id = $1
        """
        result = await connection.execute(update_query, employee_id)
        if result == "UPDATE 1":
            return {"message": "Employee promoted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Employee not found")



@app.get("/")
async def root():
    return {"Hello World"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
