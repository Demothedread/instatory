# Instatory Project

Instatory is a web application that integrates a frontend React application with a backend Flask server to process images and manage an inventory database. Users can upload images, initiate processing, and view the results.

## Prerequisites

- Node.js and npm
- Python 3.x
- Flask
- React

## Setup
To run the application:

1) Start the backend server:

    Open a terminal and navigate to the backend directory
    Run the command: python3 server.py
    Start the frontend application:

2) Open another terminal and navigate to the frontend-app directory
   
    Run the command: npm start
    Open a web browser and go to http://localhost:3000 to view the application

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Flask server:
   ```bash
   python server.py
   ```

### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend-app
   ```
2. Install Node.js dependencies:
   ```bash
   npm install
   ```
3. Start the React application:
   ```bash
   npm start
   ```

## Usage

- **Upload Images:** Use the upload button to select images for processing.
- **Process Images:** Click the "Process Images" button to send images to the backend for processing.
- **View Results:** Processed images will be removed from the list, and results will be displayed.

## Deployment

### Frontend

To build the React application for production, run:
```bash
npm run build
```

### Backend

Deploy the Flask server using a WSGI server like Gunicorn.

## Additional Features

- **Database Management:** Load and export SQL or XML databases.
- **UI Enhancements:** The application features a vaporwave color scheme for an attractive and intuitive user interface.

## Troubleshooting

- Ensure all dependencies are installed.
- Check that the backend server is running before starting the frontend.
- Verify API endpoints are correctly configured.

If you encounter any issues, please reach out to the project maintainers for assistance.
