# Printing Kiosk System

## Goal
The Printing Kiosk System is designed to provide an automated, self-service printing solution. The primary goal is to allow users to send documents via WhatsApp, which the system automatically processes, converts to PDF, and sends to the printer without requiring manual intervention. It is optimized for efficient operation on Linux systems such as Lubuntu.

## Key Functionalities
*   **WhatsApp Integration**: Leverages the Evolution API to receive documents directly from WhatsApp chats.
*   **Automated Document Conversion**: Converts DOCX files to PDF using LibreOffice or Word in headless mode.
*   **Native Printing**: Utilizes the Linux CUPS printing system or SumatraPDF for reliable and native document output.
*   **User Interface**: Features a modern, web-based UI built with NiceGUI, running in Kiosk mode for a secure, distraction-free environment.
*   **Maintenance**: When sudo code is inputed a maintenance ui appears to change configuration, close the app and clear all files and databases.
*   **Turnoff**: When shutp mode is inputed it shuts the backend down.
*   **Database**: Stores transaction history and image references using PostgreSQL.
*   **Remote Access**: It can be accessed from 7777 port of your computer ip

## Tech Stack
*   **Operating System**: Lubuntu or Windows
*   **Backend**: Python (Flask)
*   **Frontend**: NiceGUI
*   **WhatsApp API**: Evolution API (Node.js)
*   **Office Suite**: LibreOffice (headless) or Microsoft Word
*   **Printing**: CUPS (Common Unix Printing System) or SumatraPDF --silent
*   **Database**: PostgreSQL

## Installation
To install on a Linux system just modify the config.json with your datas and run start.sh file, it will install and configure all by itself

## Credits
*   **WhatsApp API**: [Evolution API](https://github.com/evolution-foundation/evolution-api)[cite: 1].
*   **UI Framework**: [NiceGUI](https://nicegui.io/)[cite: 1].
