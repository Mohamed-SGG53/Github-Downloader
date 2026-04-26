# 📦 Github Downloader

## English

### 📌 Overview

**Github Downloader** is a desktop application that allows you to download any files from GitHub (full repositories or specific folders) without using Git or command-line tools.

Just paste a GitHub link, and the app will handle everything for you.

---

### 🎯 Simple Idea

Paste a GitHub URL → the app understands it → downloads files directly to your device.

---

### 🔄 How It Works

1. **Enter a GitHub link**, such as:

   * `github.com/user/repo` (full repository)
   * `github.com/user/repo/tree/main/src` (specific folder)

2. **The app analyzes the link** to detect:

   * Repository owner
   * Repository name
   * Branch
   * File path

3. **Checks repository status**:

   * Exists or not
   * Public or private
   * Requires token or not

4. **Displays repository info** (stars, forks, etc.)

5. **Click Download** and choose save location

6. **Fetches file list** using GitHub API

7. **Downloads files** using raw URLs

8. **Recreates folder structure** on your device

---

### 💡 Features

* ✅ Download full repositories or specific folders
* ✅ Smart GitHub URL detection
* ✅ Automatic public/private handling
* ✅ Real-time progress bar and file tracking
* ✅ Error handling (invalid links, rate limits, etc.)
* ✅ Clean UI — no terminal required

---

### 🖥 System Requirements

* ✅ Windows 10 (64-bit)
* ✅ Windows 11 (64-bit)
* ❌ No Git required
* ❌ No command-line usage needed

> The app runs locally and does not require advanced setup.

---

### 🛠 Built With

* Python
* Webview
* Requests (GitHub API)

---

### 📦 Build Command

For developers who want to modify or build the project:

```bash id="6k2p9x"
pyinstaller --onedir --icon=icon.ico --add-data "icon.ico;." --noconsole --name "Github Downloader" "Github Downloader.py"
```

---

### 👨‍💻 Developer

Created by: **Mohamed Hisham**

---

### 🙏 Special Thanks

* Thanks to GitHub for providing a powerful API
* Thanks to everyone who tests and reports bugs
* Special appreciation to open-source contributors ❤️

---

---

# 📦 Github Downloader

## العربية

### 📌 نظرة عامة

**Github Downloader** هو تطبيق سطح مكتب يتيح لك تحميل أي ملفات من GitHub (سواء مستودع كامل أو مجلد محدد) بدون الحاجة لاستخدام Git أو الأوامر الطرفية.

فقط ضع الرابط، والتطبيق سيتولى كل شيء.

---

### 🎯 الفكرة ببساطة

تلصق رابط GitHub → التطبيق يفهمه → يتم تحميل الملفات مباشرة إلى جهازك.

---

### 🔄 كيف يعمل؟

1. **أدخل رابط GitHub** مثل:

   * `github.com/user/repo` (مستودع كامل)
   * `github.com/user/repo/tree/main/src` (مجلد محدد)

2. **التطبيق يحلل الرابط** ويحدد:

   * مالك المستودع
   * اسم المستودع
   * الفرع
   * المسار

3. **يتحقق من حالة المستودع**:

   * موجود أم لا
   * عام أم خاص
   * هل يحتاج Token

4. **يعرض معلومات المستودع** (النجوم، المتفرعات، إلخ)

5. **اضغط Download** واختر مكان الحفظ

6. **يجلب قائمة الملفات** باستخدام GitHub API

7. **يحمّل الملفات** عبر روابط الـ raw

8. **ينشئ نفس هيكل المجلدات** على جهازك

---

### 💡 المميزات

* ✅ تحميل مستودع كامل أو مجلد محدد
* ✅ فهم ذكي لروابط GitHub
* ✅ التعامل التلقائي مع المستودعات العامة والخاصة
* ✅ شريط تقدم مباشر أثناء التحميل
* ✅ التعامل مع الأخطاء (روابط خاطئة، Rate Limit، إلخ)
* ✅ واجهة بسيطة بدون الحاجة للـ Terminal

---

### 🖥 متطلبات التشغيل

* ✅ ويندوز 10 (64 بت)
* ✅ ويندوز 11 (64 بت)
* ❌ لا يحتاج Git
* ❌ لا يحتاج استخدام سطر الأوامر

> التطبيق يعمل محليًا بدون إعدادات معقدة.

---

### 🛠 تم التطوير باستخدام

* Python
* Webview
* Requests (GitHub API)

---

### 📦 أمر البناء

لأي شخص يريد التعديل أو بناء المشروع:

```bash id="2c7n4m"
pyinstaller --onedir --icon=icon.ico --add-data "icon.ico;." --noconsole --name "Github Downloader" "Github Downloader.py"
```

---

### 👨‍💻 المطور

تم الإنشاء بواسطة: **محمد هشام**

---

### 🙏 شكر خاص

* شكرًا لـ GitHub على الـ API القوي
* شكرًا لكل من يقوم بالتجربة والإبلاغ عن الأخطاء
* تقدير خاص لمجتمع المصادر المفتوحة ❤️

---
