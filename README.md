# Printing Kiosk System

## Goal
The Printing Kiosk System is designed to provide an automated, self-service printing solution. The primary goal is to allow users to send documents via WhatsApp, Email or USB key which the system automatically processes, converts to PDF, and sends to the printer without requiring manual intervention. (Windows Only)

## Key Functionalities
*   **WhatsApp Integration**: Leverages the Evolution API to receive documents directly from WhatsApp chats.
*   **Automated Document Conversion**: Converts DOCX files to PDF using LibreOffice or Word in headless mode.
*   **Native Printing**: Utilizes SumatraPDF for reliable and native document output.
*   **User Interface**: Features a modern, web-based UI built with NiceGUI, running in Kiosk mode for a secure, distraction-free environment.
*   **Maintenance**: When sudo code is inputed a maintenance ui appears to change configuration, close the app and clear all files and databases.
*   **Turnoff**: When shutp mode is inputed it shuts the backend down.
*   **Database**: Stores transaction history and image references using PostgreSQL.
*   **Remote Access**: It can be accessed from 7777 port of your computer ip

## Tech Stack
*   **Operating System**: Windows
*   **Backend**: Python (Flask)
*   **Frontend**: NiceGUI
*   **WhatsApp API**: Evolution API (Node.js)
*   **Office Suite**: LibreOffice (headless) or Microsoft Word
*   **Printing**:  SumatraPDF --silent
*   **Database**: PostgreSQL

## Installation
* Modify the config.json with your datas and run start.bat file

## Credits
*   **WhatsApp API**: [Evolution API](https://github.com/evolution-foundation/evolution-api).
*   **UI Framework**: [NiceGUI](https://nicegui.io/).
*   Gemini & Copilot as coding companion
