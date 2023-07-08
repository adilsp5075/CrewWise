from fastapi import FastAPI,HTTPException
from pydantic import BaseModel
from datetime import date
from database import connect_to_db
    
app = FastAPI()

class EmployeeCreate(BaseModel):
    name: str
    email: str
    contact_number: str
    date_of_joining: date
    years_of_experience: int


@app.on_event("startup")
async def startup():
    app.state.connection_pool = await connect_to_db()

@app.on_event("shutdown")
async def shutdown():
    await app.state.connection_pool.close()


@app.post("/employees")
async def create_employee(employee: EmployeeCreate):
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
        
# Endpoint to update an employee by ID
@app.put("/employees/{employee_id}")
async def update_employee(employee_id: int, employee: EmployeeCreate):
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



# @app.delete("/employees/clear")
# async def clear_employee_data():
#     async with app.state.connection_pool.acquire() as connection:
#         query = """
#             DELETE FROM Employee
#         """
#         await connection.execute(query)
#         return {"message": "Employee data cleared successfully"}


@app.get("/")
async def root():
    return {"Hello World"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
