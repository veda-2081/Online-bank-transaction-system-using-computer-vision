
# 💳 Online Bank Transaction System Using Computer Vision

## 📌 Project Description

This project is a secure ATM system that replaces traditional card + PIN authentication with **facial recognition**, **password hashing**, and **OTP verification** using Python and Computer Vision techniques. It uses real-time webcam input for facial recognition and ensures multi-factor authentication.

---

## 🧩 Features

- 🔒 Multi-factor authentication (Password + Face + OTP)
- 🧠 Real-time facial recognition using CNN embeddings
- 🧾 User-friendly GUI using Tkinter
- 📁 Local data storage using CSV files
- 📤 OTP verification using Twilio API
- 🛡️ Secure password storage with PBKDF2-HMAC-SHA256

---

## ⚙️ Software Installation & Setup

### 📌 Pre-requisites

- Python 3.7+
- Internet connection for OTP delivery via Twilio
- Webcam (internal or USB)

### 💾 Install Python (if not installed)
Download from: https://www.python.org/downloads/

---

### 📦 Required Libraries

Open terminal or command prompt and run:

```bash
pip install opencv-python
pip install face-recognition
pip install numpy
pip install pillow
pip install twilio
```

### (Optional) For better face recognition performance:
```bash
pip install dlib
```

> Note: Installing `dlib` may require a C++ compiler. Use `pip install cmake` and `pip install dlib` or use a precompiled wheel for your system.

---

## 📁 File Structure

```
├── main.py               # Main script to launch GUI
├── users.csv             # Stores user credentials, embeddings, balances
├── faces/                # Folder containing stored face images
├── otp_module.py         # Twilio OTP integration
├── gui/                  # All GUI-related modules
├── README.md
```

---

## 🔐 Authentication Process

1. **Registration**
   - Enter name, password, phone number
   - Capture face via webcam
   - Save face encoding and hashed password in CSV

2. **Login**
   - Verify password
   - Capture and compare face with stored embedding
   - Send OTP to registered phone
   - Verify OTP

---

## 🚀 How to Run the Project

```bash
python 1.py
```

---

## 🔑 Twilio Configuration (for OTP)

1. Create an account at [Twilio](https://www.twilio.com/)
2. Get your `Account SID`, `Auth Token`, and phone number
3. Add them in your `otp_module.py` file:

```python
from twilio.rest import Client

account_sid = 'YOUR_TWILIO_SID'
auth_token = 'YOUR_TWILIO_AUTH_TOKEN'
twilio_number = 'YOUR_TWILIO_PHONE'

client = Client(account_sid, auth_token)

message = client.messages.create(
    body="Your OTP is: 123456",
    from_=twilio_number,
    to=receiver_number
)
```

---
## 🎥 Demo Video

👉 [Watch the video demo](media/WhatsApp Video 2025-06-25 at 14.20.41.mp4)

---

## 🔮 Future Enhancements

- Add liveness detection (e.g. blink detection)
- Replace CSV with SQLite or MySQL
- Integrate mobile app
- Enhance low-light image recognition
