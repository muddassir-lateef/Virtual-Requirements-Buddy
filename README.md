# Virtual Requirements Buddy (VRB)

An AI-powered assistant designed to help non-technical people write and structure software requirements engineering documents.

## Features

- **Requirements Guidance**: Helps users understand and articulate software requirements
- **Web Search**: Finds relevant information, best practices, and examples
- **Document Generation**: Creates structured requirements documents for download
- **Interactive Chat**: Natural language interface for requirements gathering

## Docker

sudo docker build -t vrb-app:latest .

sudo docker run --env-file .env -p 8080:8080 vrb-app:latest