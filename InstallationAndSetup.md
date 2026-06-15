# Installation and Local Setup Guide:

This document guides developers through setting up the local workspace environment for both frontend and backend development.

## Prerequisites:

Ensure that you have installed the following system dependencies:
- Python: Version 3.10 or higher.
- Node.js: Version 18 or higher.
- Package Managers: NPM and Pip.
- Docker: Optional, used to run PostgreSQL databases locally.

## Backend Installation Steps:

Set up the backend server:

### 1. Initialize Virtual Environment:
- Open a terminal at the repository root.
- Run `python -m venv .venv` to create a virtual directory.
- Activate the virtual directory by running `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on Linux or MacOS.

### 2. Install Dependencies:
- Upgrade pip by running `python -m pip install --upgrade pip`.
- Install packages by running `pip install -r Backend/requirements.txt`.

### 3. Configure Environment Variables:
- Copy the template file: `cp .env.example .env`.
- Open the `.env` file to configure configuration parameters.
  - `GEMINI_API_KEY`: API token from Google AI Studio.
  - `TWILIO_ACCOUNT_SID`: Account string from Twilio Console.
  - `TWILIO_AUTH_TOKEN`: Security token from Twilio Console.
  - `TWILIO_PHONE_NUMBER`: Twilio sandbox WhatsApp sender address.
  - `USER_PHONE_NUMBER`: Your verified WhatsApp recipient address.

### 4. Start Server:
- Start the server using Uvicorn: `python -m uvicorn Backend.MainFastApi:app --port 8000`.
- Verify the server is running by opening `http://localhost:8000/docs` in your browser.

## Frontend Installation Steps:

Set up the React application:

### 1. Install Node Packages:
- Navigate to the frontend directory: `cd Frontend`.
- Install dependencies: `npm install`.

### 2. Run Development Server:
- Start the local dev server: `npm run dev`.
- Open `http://localhost:5173` in your browser.
- Select the demo user option on the login page.

### 3. Google OAuth Setup:
- Access the Google Cloud Console.
- Navigate to APIs and Services, then select Credentials.
- Select your OAuth 2.0 Client ID or create a new one.
- Under Authorized JavaScript Origins, add `http://localhost:5173`.
- Under Authorized Redirect URIs, add `http://localhost:5173/login`.
- Update `clientId` in `Frontend/Src/pages/Login.jsx` and `GOOGLE_CLIENT_ID` in `.env` if utilizing a personalized Client ID.

## Running Tests:

Run the automated test suites:

### 1. Backend Verification:
- Discover unit tests using unittest: `python -m unittest discover -s Backend/Tests -p "*.py"`.

### 2. Frontend Verification:
- Run the frontend tests: `npm run test`.
