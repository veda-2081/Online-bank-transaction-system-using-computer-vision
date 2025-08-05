import os
import random
import tkinter as tk
from tkinter import messagebox
from tkinter import Toplevel, Label, Entry, Button
import cv2
import csv
import hashlib
from PIL import Image, ImageTk
import face_recognition
import traceback
from twilio.rest import Client

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

TWILIO_ACCOUNT_SID = 'ACb60284b56224a2086fe8c1dba058e39c'
TWILIO_AUTH_TOKEN = 'f1e89bdaab7685a268a6bfaecbae5564'
TWILIO_PHONE_NUMBER = '+16509772717'

CSV_FILE = "user_data.csv"
IMAGE_DIR = "faces"
PRIMARY_COLOR = "#00A3E0"
SECONDARY_COLOR = "#E2F0F7"
TEXT_COLOR = "#333333"
BUTTON_COLOR = "#00A3E0"
BUTTON_HOVER_COLOR = "#0082C9"
FONT_NAME = "Arial"

os.makedirs(IMAGE_DIR, exist_ok=True)

def hash_password(pwd, salt=None):
    if salt is None:
        salt = os.urandom(16)
    pwd_bytes = pwd.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt, 100000)
    return salt.hex() + ':' + hashed.hex()

def verify_password(stored_password, provided_password):
    try:
        salt, hashed = stored_password.split(':')
        salt_bytes = bytes.fromhex(salt)
        provided_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt_bytes, 100000)
        return provided_hash.hex() == hashed
    except Exception:
        return False

def load_users():
    users = {}
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, "r", newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    users[row['name']] = row
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load user data:\n{e}")
    return users

def save_users(users):
    try:
        with open(CSV_FILE, 'w', newline='') as f:
            fieldnames = ['name', 'password', 'face_path', 'balance', 'phone']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for user in users.values():
                writer.writerow(user)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save user data:\n{e}")

def on_enter_button(e):
    e.widget['background'] = BUTTON_HOVER_COLOR

def on_leave_button(e):
    e.widget['background'] = BUTTON_COLOR

class FaceCaptureWindow:
    def __init__(self, parent, title):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.resizable(False, False)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Cannot access camera")
            self.top.destroy()
            self.captured_img = None
            return
        self.label = tk.Label(self.top)
        self.label.pack()
        self.btn_frame = tk.Frame(self.top)
        self.btn_frame.pack(fill='x', pady=5)
        self.capture_btn = tk.Button(self.btn_frame, text="Capture (Space)", command=self.capture)
        self.capture_btn.pack(side='left', padx=5)
        self.cancel_btn = tk.Button(self.btn_frame, text="Cancel (ESC)", command=self.on_cancel)
        self.cancel_btn.pack(side='left', padx=5)
        self.captured_img = None
        self.is_capturing = True
        self.top.bind('<space>', lambda e: self.capture())
        self.top.bind('<Escape>', lambda e: self.on_cancel())
        self.update_frame()
    def update_frame(self):
        if not self.is_capturing:
            return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.label.imgtk = imgtk
            self.label.config(image=imgtk)
        self.top.after(10, self.update_frame)
    def capture(self):
        if hasattr(self, 'current_frame'):
            self.captured_img = self.current_frame.copy()
        self.close()
    def on_cancel(self):
        self.captured_img = None
        self.close()
    def close(self):
        self.is_capturing = False
        if self.cap.isOpened():
            self.cap.release()
        self.top.grab_release()

        self.top.destroy()

def capture_face_image(parent, name):
    fcw = FaceCaptureWindow(parent, f"Capture Face - {name}")
    parent.wait_window(fcw.top)
    face_img = fcw.captured_img
    if face_img is not None:
        rgb_face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_face_img)
        if len(face_locations) == 0:
            messagebox.showerror("Error", "No face detected. Please try again.")
            return None
        top, right, bottom, left = max(face_locations, key=lambda rect: (rect[2]-rect[0])*(rect[1]-rect[3]))
        face_crop = rgb_face_img[top:bottom, left:right]
        face_path = os.path.join(IMAGE_DIR, f"{name}.jpg")
        face_crop_bgr = cv2.cvtColor(face_crop, cv2.COLOR_RGB2BGR)
        try:
            cv2.imwrite(face_path, face_crop_bgr)
            return face_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save face image:\n{e}")
            return None
    else:
        return None

def get_face_embedding(face_img):
    try:
        encodings = face_recognition.face_encodings(face_img)
        if len(encodings) == 0:
            return None
        return encodings[0]
    except Exception:
        traceback.print_exc()
        return None

def verify_face(enrolled_embedding, test_embedding, tolerance=0.45):
    try:
        if enrolled_embedding is None or test_embedding is None:
            return False
        distance = face_recognition.face_distance([enrolled_embedding], test_embedding)[0]
        return distance <= tolerance
    except Exception:
        traceback.print_exc()
        return False

class OTPVerifier(tk.Toplevel):
    def __init__(self, parent, phone_number, on_verified):
        super().__init__(parent)
        self.geometry("400x250")
        self.title("OTP Verification")
        self.phone_number = phone_number
        self.otp = random.randint(1000, 9999)
        self.on_verified = on_verified
        self.transient(parent)
        self.grab_set()
        self.lift()
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                to=self.phone_number,
                from_=TWILIO_PHONE_NUMBER,
                body=f"Your OTP is {self.otp}"
            )
            messagebox.showinfo("OTP Sent", f"OTP sent to {self.phone_number}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send OTP: {str(e)}")
            self.destroy()
        tk.Label(self, text="Enter OTP:", font=(FONT_NAME, 16), bg=SECONDARY_COLOR, fg=TEXT_COLOR).pack(pady=10)
        
        self.otp_entry = tk.Entry(self, font=(FONT_NAME, 16))
        self.otp_entry.pack(pady=10)
        self.verify_button = tk.Button(self, text="Verify", font=(FONT_NAME, 16), bg=BUTTON_COLOR, fg='white', command=self.verify_otp)
        self.verify_button.pack(pady=10)
    def verify_otp(self):
        try:
            user_input = int(self.otp_entry.get())
            if user_input == self.otp:
                messagebox.showinfo("Success", "OTP Verified Successfully!")
                self.destroy()
                self.on_verified()
            else:
                messagebox.showerror("Error", "Incorrect OTP! Try again.")
        except ValueError:
            messagebox.showerror("Error", "Invalid OTP format!")

class ATMFaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ATM Security - Facial Recognition")
        self.root.config(bg=SECONDARY_COLOR)
        self.root.attributes('-fullscreen', True)
        self.root.resizable(False, False)
        self.users = load_users()
        self.enrolled_embeddings = {}
        self.load_all_embeddings()
        self.current_user = None
        self.main_frame = tk.Frame(root, bg=SECONDARY_COLOR)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.build_main_menu()

    def build_main_menu(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        tk.Label(self.main_frame, text="Online Transaction", font=(FONT_NAME, 28, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).pack(pady=(0, 30))
        btn_enroll = tk.Button(self.main_frame, text="Enroll", width=30, height=2, bg=BUTTON_COLOR, fg='white',
                               font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                               command=self.enroll_screen)
        btn_enroll.pack(pady=15)
        btn_enroll.bind("<Enter>", on_enter_button)
        btn_enroll.bind("<Leave>", on_leave_button)
        btn_login = tk.Button(self.main_frame, text="Login", width=30, height=2, bg=BUTTON_COLOR, fg='white',
                              font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                              command=self.login_screen)
        btn_login.pack(pady=15)
        btn_login.bind("<Enter>", on_enter_button)
        btn_login.bind("<Leave>", on_leave_button)
        btn_exit = tk.Button(self.main_frame, text="Exit", width=30, height=2, bg="#e94b3c", fg='white',
                             font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground="#b8362a",
                             command=self.root.quit)
        btn_exit.pack(pady=15)
        btn_exit.bind("<Enter>", lambda e: e.widget.config(bg="#b8362a"))
        btn_exit.bind("<Leave>", lambda e: e.widget.config(bg="#e94b3c"))

    def load_all_embeddings(self):
        for name, user in self.users.items():
            face_path = user.get('face_path', '')
            if face_path and os.path.exists(face_path):
                try:
                    face_img = face_recognition.load_image_file(face_path)
                    embedding = get_face_embedding(face_img)
                    if embedding is not None:
                        self.enrolled_embeddings[name] = embedding
                except Exception:
                    traceback.print_exc()

    def clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def enroll_screen(self):
        self.clear_frame()
        outer_frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR)
        outer_frame.pack(expand=True)
        frame = tk.Frame(outer_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack()
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        tk.Label(frame, text="Enroll New User", font=(FONT_NAME, 24, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).grid(row=0, column=0, columnspan=2, pady=15)
        tk.Label(frame, text="Full Name:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=1, column=0, sticky="")
        name_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, relief='solid', borderwidth=1)
        name_entry.grid(row=1, column=1, pady=8)
        tk.Label(frame, text="Password:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=2, column=0, sticky="")
        pwd_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, show="*", relief='solid', borderwidth=1)
        pwd_entry.grid(row=2, column=1, pady=8)
        tk.Label(frame, text="Phone Number:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=3, column=0, sticky="")
        phone_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, relief='solid', borderwidth=1)
        phone_entry.grid(row=3, column=1, pady=8)

        def after_otp_verified():
            # After OTP verified, proceed to face capture
            name = name_entry.get().strip()
            pwd = pwd_entry.get().strip()
            phone = phone_entry.get().strip()
            face_path = capture_face_image(self.root, name)
            if not face_path:
                return
            hashed_pwd = hash_password(pwd)
            user = {'name': name, 'password': hashed_pwd, 'face_path': face_path, 'balance': '0', 'phone': phone}
            self.users[name] = user
            save_users(self.users)
            face_img = face_recognition.load_image_file(face_path)
            embedding = get_face_embedding(face_img)
            if embedding is not None:
                self.enrolled_embeddings[name] = embedding
            messagebox.showinfo("Success", "User enrolled successfully!")
            self.build_main_menu()

        def enroll_action():
            name = name_entry.get().strip()
            pwd = pwd_entry.get().strip()
            phone = phone_entry.get().strip()
            if not name or not pwd or not phone:
                messagebox.showwarning("Warning", "Please fill all the fields")
                return
            if name in self.users:
                messagebox.showwarning("Warning", "User already exists")
                return
            # Send OTP before face capture
            OTPVerifier(self.root, phone, after_otp_verified)

        btn_frame = tk.Frame(frame, bg=SECONDARY_COLOR)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=30)
        btn_enroll = tk.Button(btn_frame, text="Enroll", width=15, height=2, bg=BUTTON_COLOR, fg='white',
                               font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                               command=enroll_action)
        btn_enroll.pack(side="left", padx=10)
        btn_enroll.bind("<Enter>", on_enter_button)
        btn_enroll.bind("<Leave>", on_leave_button)
        btn_back = tk.Button(btn_frame, text="Back", width=15, height=2, bg="#888", fg='white',
                             font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground="#666",
                             command=self.build_main_menu)
        btn_back.pack(side="left", padx=10)
        btn_back.bind("<Enter>", lambda e: e.widget.config(bg="#666"))
        btn_back.bind("<Leave>", lambda e: e.widget.config(bg="#888"))
        
    def login_screen(self):
        self.clear_frame()
        outer_frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR)
        outer_frame.pack(expand=True)
        frame = tk.Frame(outer_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack()
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        tk.Label(frame, text="User Login", font=(FONT_NAME, 24, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).grid(row=0, column=0, columnspan=2, pady=15)
        tk.Label(frame, text="Full Name:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=1, column=0, sticky="")
        name_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, relief='solid', borderwidth=1)
        name_entry.grid(row=1, column=1, pady=8)
        tk.Label(frame, text="Password:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=2, column=0, sticky="")
        pwd_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, show="*", relief='solid', borderwidth=1)
        pwd_entry.grid(row=2, column=1, pady=8)
        tk.Label(frame, text="Phone Number:", font=(FONT_NAME, 16), fg=TEXT_COLOR, bg=SECONDARY_COLOR).grid(row=3, column=0, sticky="")
        phone_entry = tk.Entry(frame, font=(FONT_NAME, 16), width=30, relief='solid', borderwidth=1)
        phone_entry.grid(row=3, column=1, pady=8)

        def after_otp_verified():
            self.current_user = name_entry.get().strip()
            face_path = capture_face_image(self.root, self.current_user + " (Login)")
            if not face_path:
                return
            face_img = face_recognition.load_image_file(face_path)
            test_embedding = get_face_embedding(face_img)
            enrolled_embedding = self.enrolled_embeddings.get(self.current_user)
            if enrolled_embedding is None or test_embedding is None:
                messagebox.showerror("Error", "Face data missing for verification.")
                try:
                    os.remove(face_path)
                except:
                    pass
                return
            if verify_face(enrolled_embedding, test_embedding):
                messagebox.showinfo("Success", f"Welcome {self.current_user}!")
                self.dashboard_screen()
            else:
                messagebox.showwarning("Warning", "Face verification failed! Access denied.")
            try:
                os.remove(face_path)
            except:
                pass

        def login_action():
            name = name_entry.get().strip()
            pwd = pwd_entry.get().strip()
            phone = phone_entry.get().strip()
            if not name or not pwd or not phone:
                messagebox.showwarning("Warning", "Please fill all the fields")
                return
            if name not in self.users:
                messagebox.showwarning("Warning", "User does not exist")
                return
            stored_password = self.users[name]['password']
            if not verify_password(stored_password, pwd):
                messagebox.showwarning("Warning", "Incorrect password")
                return
            user_phone = self.users[name]['phone']
            if phone != user_phone:
                messagebox.showwarning("Warning", "Phone number does not match registered number")
                return
            OTPVerifier(self.root, phone, after_otp_verified)

        btn_frame = tk.Frame(frame, bg=SECONDARY_COLOR)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=30)
        btn_login = tk.Button(btn_frame, text="Login", width=15, height=2, bg=BUTTON_COLOR, fg='white',
                              font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                              command=login_action)
        btn_login.pack(side="left", padx=10)
        btn_login.bind("<Enter>", on_enter_button)
        btn_login.bind("<Leave>", on_leave_button)
        btn_back = tk.Button(btn_frame, text="Back", width=15, height=2, bg="#888", fg='white',
                             font=(FONT_NAME, 16, 'bold'), borderwidth=0, activebackground="#666",
                             command=self.build_main_menu)
        btn_back.pack(side="left", padx=10)
        btn_back.bind("<Enter>", lambda e: e.widget.config(bg="#666"))
        btn_back.bind("<Leave>", lambda e: e.widget.config(bg="#888"))

    def dashboard_screen(self):
        self.clear_frame()
        frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f"Welcome, {self.current_user}", font=(FONT_NAME, 20, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).pack(pady=15)
        btns = [
            ("Withdraw", self.withdraw_screen),
            ("Deposit", self.deposit_screen),
            ("Check Balance", self.balance_screen),
            ("Logout", self.logout)
        ]
        for text, cmd in btns:
            btn = tk.Button(frame, text=text, width=30, height=2, bg=BUTTON_COLOR, fg='white',
                            font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                            command=cmd)
            btn.pack(pady=8)
            btn.bind("<Enter>", on_enter_button)
            btn.bind("<Leave>", on_leave_button)
    def withdraw_screen(self):
        self.clear_frame()
        frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Withdraw Amount", font=(FONT_NAME, 20, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).pack(pady=15)
        amount_entry = tk.Entry(frame, font=(FONT_NAME, 14), width=30, relief='solid', borderwidth=1)
        amount_entry.pack(pady=8)

        def withdraw_action():
            amt_str = amount_entry.get().strip()
            if not amt_str.isdigit():
                messagebox.showwarning("Warning", "Enter a valid amount")
                return
            amt = int(amt_str)
            if amt <= 0:
                messagebox.showwarning("Warning", "Amount must be positive")
                return
            balance = float(self.users[self.current_user]['balance'])
            if amt > balance:
                messagebox.showwarning("Warning", "Insufficient balance")
                return
            balance -= amt
            self.users[self.current_user]['balance'] = str(balance)
            save_users(self.users)
            messagebox.showinfo("Success", f"Withdrawal successful! New balance: {balance:.2f}")
            self.dashboard_screen()

        btn_frame = tk.Frame(frame, bg=SECONDARY_COLOR)
        btn_frame.pack(pady=20)

        btn_withdraw = tk.Button(btn_frame, text="Withdraw", width=15, height=2, bg=BUTTON_COLOR, fg='white',
                                 font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                                 command=withdraw_action)
        btn_withdraw.pack(side="left", padx=10)
        btn_withdraw.bind("<Enter>", on_enter_button)
        btn_withdraw.bind("<Leave>", on_leave_button)

        btn_back = tk.Button(btn_frame, text="Back", width=15, height=2, bg="#888", fg='white',
                             font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground="#666",
                             command=self.dashboard_screen)
        btn_back.pack(side="left", padx=10)
        btn_back.bind("<Enter>", lambda e: e.widget.config(bg="#666"))
        btn_back.bind("<Leave>", lambda e: e.widget.config(bg="#888"))

    def deposit_screen(self):
        self.clear_frame()
        frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Deposit Amount", font=(FONT_NAME, 20, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).pack(pady=15)
        amount_entry = tk.Entry(frame, font=(FONT_NAME, 14), width=30, relief='solid', borderwidth=1)
        amount_entry.pack(pady=8)

        def deposit_action():
            amt_str = amount_entry.get().strip()
            if not amt_str.isdigit():
                messagebox.showwarning("Warning", "Enter a valid amount")
                return
            amt = int(amt_str)
            if amt <= 0:
                messagebox.showwarning("Warning", "Amount must be positive")
                return
            balance = float(self.users[self.current_user]['balance'])
            balance += amt
            self.users[self.current_user]['balance'] = str(balance)
            save_users(self.users)
            messagebox.showinfo("Success", f"Deposit successful! New balance: {balance:.2f}")
            self.dashboard_screen()

        btn_frame = tk.Frame(frame, bg=SECONDARY_COLOR)
        btn_frame.pack(pady=20)

        btn_deposit = tk.Button(btn_frame, text="Deposit", width=15, height=2, bg=BUTTON_COLOR, fg='white',
                                font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground=BUTTON_HOVER_COLOR,
                                command=deposit_action)
        btn_deposit.pack(side="left", padx=10)
        btn_deposit.bind("<Enter>", on_enter_button)
        btn_deposit.bind("<Leave>", on_leave_button)

        btn_back = tk.Button(btn_frame, text="Back", width=15, height=2, bg="#888", fg='white',
                             font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground="#666",
                             command=self.dashboard_screen)
        btn_back.pack(side="left", padx=10)
        btn_back.bind("<Enter>", lambda e: e.widget.config(bg="#666"))
        btn_back.bind("<Leave>", lambda e: e.widget.config(bg="#888"))

    def balance_screen(self):
        self.clear_frame()
        frame = tk.Frame(self.main_frame, bg=SECONDARY_COLOR, padx=20, pady=20)
        frame.pack(fill="both", expand=True)
        
        balance = float(self.users[self.current_user]['balance'])
        
        # Check if balance is below 1000 and show alert
        if balance < 1000:
            messagebox.showwarning("Balance Alert", f"Your balance is below 1000. Current balance: {balance:.2f}")
    
        tk.Label(frame, text=f"Your current balance is: {balance:.2f}", font=(FONT_NAME, 20, 'bold'), fg=PRIMARY_COLOR, bg=SECONDARY_COLOR).pack(pady=15)
    
        btn_back = tk.Button(frame, text="Back", width=15, height=2, bg="#888", fg='white',
                             font=(FONT_NAME, 14, 'bold'), borderwidth=0, activebackground="#666",
                             command=self.dashboard_screen)
        btn_back.pack(pady=20)
        btn_back.bind("<Enter>", lambda e: e.widget.config(bg="#666"))
        btn_back.bind("<Leave>", lambda e: e.widget.config(bg="#888"))


    def logout(self):
        self.current_user = None
        messagebox.showinfo("Logout", "You have been logged out.")
        self.build_main_menu()
        
if __name__ == "__main__":
    root = tk.Tk()
    app = ATMFaceRecognitionApp(root)
    root.mainloop()

