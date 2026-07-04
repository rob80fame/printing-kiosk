# printing-kiosk
This project aims to modernize manual copy shop operations by offloading document reception and print configuration to an automated system. By separating the Backend (Bot) from the Frontend (Kiosk), the system remains modular, scalable, and easy to maintain.

# Architecture
The system is built on a decoupled architecture:

Backend: A Python-based bot that handles WhatsApp communication via the Evolution API.

Database: A central database acts as the bridge between the Backend and Frontend.

Frontend: A Kiosk-specific interface that retrieves user files based on a unique code and facilitates the print process.

# Backend (The WhatsApp Bot)

Message Processing: Intercepts incoming messages and documents from WhatsApp.
Automatic Media Handling: Downloads, decrypts, and categorizes documents/images into local storage.
Session Management: Generates a unique, short-lived code for every user session.
Database Integration: Maps WhatsApp JIDs (phone numbers) to document paths and generated codes.
User Feedback: Automatically replies to the user with the generated code required for printing.

# Frontend (The Kiosk Interface)
Code Authentication: Users input their unique code to retrieve their files.
Preview & Pricing: Real-time preview of the document and dynamic cost calculation based on a predefined price list.
Print Configuration:
Color mode: Color vs. Black & White.
Format: A4, A3, etc.
Duplex: Front only vs. Double-sided (Both sides).
Layout: Number of pages per sheet.
Automated Dispatch: Once settings are confirmed, the system interfaces with SumatraPDF printer drivers to execute the print job.

# Workflow
User sends a file via WhatsApp.
Backend processes the file, saves it, generates a code, and replies via WhatsApp.
User visits the Kiosk, enters the code on the Frontend.
Frontend fetches the file details from the Database, calculates the price, and displays an interactive print settings panel.
User configures the print job and confirms.
System prints the document.

Backend: [Active/In-Progress]

Frontend: [Active/In-Progress]

This project is designed to minimize manual interaction at the front desk, allowing staff to focus on high-value tasks rather than file management and formatting.