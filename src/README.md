# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Teacher login for registering and unregistering students

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                      | Log in as a teacher                                                 |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student (teacher login required)                         |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher login required)                    |
| PATCH  | `/activities/{activity_name}/configuration` | Configure enrollment mode and leave policy (teacher login required) |
| POST   | `/activities/{activity_name}/teams` | Create a team for team-based activities (`X-Student-Email` must match leader, or teacher login) |
| POST   | `/activities/{activity_name}/teams/{team_name}/join` | Join an existing team (`X-Student-Email` must match joining student, or teacher login) |
| POST   | `/activities/{activity_name}/teams/{team_name}/members` | Team leader adds a member (`X-Student-Email` must match leader, or teacher login) |
| GET    | `/activities/{activity_name}/participants` | View activity participants grouped by team (teacher login required) |
| GET    | `/activities/{activity_name}/enrollment?email=student@mergington.edu` | View a student's enrollment (`X-Student-Email` must match email, or teacher login) |
| DELETE | `/activities/{activity_name}/enrollment?email=student@mergington.edu` | Leave current enrollment (`X-Student-Email` must match email, or teacher login) |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Enrollment type (`individual` or `team`)
   - Maximum number of participants allowed
   - Leave policy (`allow_student_leave`)
   - Individual activities: list of student emails who are signed up
   - Team activities: team definitions (leader + members) with team size constraints

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.

Teacher credentials are stored in `teachers.json` for this exercise. The default account is `teacher` with password `mergington-teacher`.

Student self-service endpoints accept either teacher authorization or a matching `X-Student-Email` header.
