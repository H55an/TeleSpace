# database.py

import sqlite3
from config import DB_NAME # نستورد اسم قاعدة البيانات من ملف الإعدادات

def add_user_if_not_exists(user_id: int, first_name: str):
    """
    تضيف مستخدمًا جديدًا إلى جدول users إذا لم يكن موجودًا بالفعل.
    Args:
        user_id (int): معرف المستخدم الفريد من تيليجرام.
        first_name (str): الاسم الأول للمستخدم.
    """
    try:
        # نتصل بقاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 1. التحقق من وجود المستخدم
        #    نبحث عن صف في جدول users حيث user_id يطابق المعرف الذي تم تمريره
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        
        # .fetchone() تقوم بجلب نتيجة واحدة فقط من البحث
        existing_user = cursor.fetchone()

        # 2. إضافة المستخدم إذا لم يكن موجودًا
        if not existing_user:
            # نستخدم علامات الاستفهام (?) لمنع هجمات SQL Injection
            # هذه هي الطريقة الآمنة لتمرير المتغيرات إلى أوامر SQL
            cursor.execute("INSERT INTO users (user_id, first_name) VALUES (?, ?)", 
                           (user_id, first_name))
            conn.commit() # نحفظ التغيير
            print(f"تمت إضافة مستخدم جديد: {first_name} ({user_id})")
        else:
            print(f"المستخدم {first_name} ({user_id}) موجود بالفعل.")

    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات: {e}")
    finally:
        # 3. التأكد من إغلاق الاتصال دائمًا
        if conn:
            conn.close()


def add_section(user_id: int, section_name: str):
    """
    تضيف قسمًا جديدًا مرتبطًا بمستخدم معين.
    Args:
        user_id (int): معرف المستخدم صاحب القسم.
        section_name (str): اسم القسم الجديد.
    """
    try:
        # 1. نتصل بقاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 2. تنفيذ أمر الإضافة (INSERT)
        #    نضيف صفًا جديدًا إلى جدول sections
        #    ونقوم بتمرير user_id و section_name كقيم
        cursor.execute("INSERT INTO sections (user_id, section_name) VALUES (?, ?)",
                       (user_id, section_name))
        
        # 3. حفظ التغيير بشكل دائم في قاعدة البيانات
        conn.commit()
        print(f"تمت إضافة قسم '{section_name}' للمستخدم {user_id} بنجاح.")

    except sqlite3.Error as e:
        # في حال حدوث أي خطأ في قاعدة البيانات، نقوم بطباعته
        print(f"حدث خطأ في قاعدة البيانات عند إضافة قسم: {e}")
    finally:
        # 4. في كل الأحوال (سواء نجحت العملية أم فشلت)، نغلق الاتصال
        if conn:
            conn.close()


def add_folder(owner_user_id: int, folder_name: str, section_id: int = None):
    """
    تضيف مجلدًا جديدًا. إذا تم توفير section_id، يتم وضع المجلد داخل هذا القسم.
    وإلا، يتم اعتباره مجلدًا رئيسيًا.
    Args:
        owner_user_id (int): معرف المستخدم مالك المجلد.
        folder_name (str): اسم المجلد الجديد.
        section_id (int, optional): معرف القسم الذي ينتمي إليه المجلد. Defaults to None.
    """
    try:
        # 1. نتصل بقاعدة البيانات
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 2. تنفيذ أمر الإضافة (INSERT)
        #    لاحظ أننا نضيف إلى جدول folders ونحدد الأعمدة الثلاثة
        cursor.execute("INSERT INTO folders (owner_user_id, folder_name, section_id) VALUES (?, ?, ?)",
                       (owner_user_id, folder_name, section_id))
        
        # 3. حفظ التغيير بشكل دائم
        conn.commit()
        if section_id:
            print(f"تمت إضافة مجلد '{folder_name}' للمستخدم {owner_user_id} داخل القسم {section_id}.")
        else:
            print(f"تمت إضافة مجلد رئيسي '{folder_name}' للمستخدم {owner_user_id}.")

    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند إضافة مجلد: {e}")
    finally:
        # 4. إغلاق الاتصال في كل الأحوال
        if conn:
            conn.close()


def get_user_sections(user_id: int):
    """
    تجلب كل الأقسام الخاصة بمستخدم معين.
    Returns:
        list: قائمة من الصفوف (tuples)، كل صف يحتوي على (section_id, section_name).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        # نستخدم row_factory لجعل النتائج أكثر قابلية للقراءة (مثل القواميس)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # SELECT: اختر الأعمدة section_id, section_name
        # FROM sections: من جدول الأقسام
        # WHERE user_id = ?: بشرط أن يكون user_id مطابقًا للمستخدم المطلوب
        cursor.execute("SELECT section_id, section_name FROM sections WHERE user_id = ?", (user_id,))
        sections = cursor.fetchall() # .fetchall() تجلب كل النتائج المطابقة
        return sections
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب الأقسام: {e}")
        return [] # نرجع قائمة فارغة في حالة حدوث خطأ
    finally:
        if conn:
            conn.close()

def get_user_root_folders(user_id: int):
    """
    تجلب كل المجلدات الرئيسية (التي لا تنتمي لقسم) الخاصة بمستخدم معين.
    Returns:
        list: قائمة من الصفوف، كل صف يحتوي على (folder_id, folder_name).
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WHERE section_id IS NULL: هذا هو الشرط السحري الذي يختار فقط المجلدات
        # التي لا ترتبط بأي قسم (قيمتها NULL)
        cursor.execute(
            "SELECT folder_id, folder_name FROM folders WHERE owner_user_id = ? AND section_id IS NULL",
            (user_id,)
        )
        folders = cursor.fetchall()
        return folders
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب المجلدات الرئيسية: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_user_folders(user_id: int):
    """
    تجلب كل مجلدات المستخدم مع أسماء الأقسام التي تنتمي إليها (إن وجدت).
    Returns:
        list: قائمة من الصفوف، كل صف يحتوي على (folder_id, folder_name, section_name).
              section_name سيكون None إذا كان المجلد رئيسيًا.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # نستخدم LEFT JOIN لربط المجلدات بالأقسام
        # سيتم جلب كل المجلدات، حتى لو لم تكن مرتبطة بقسم (سيكون section_name هو NULL)
        cursor.execute("""
            SELECT 
                f.folder_id, 
                f.folder_name, 
                s.section_name 
            FROM 
                folders f
            LEFT JOIN 
                sections s ON f.section_id = s.section_id
            WHERE 
                f.owner_user_id = ?
        """, (user_id,))
        
        all_folders = cursor.fetchall()
        return all_folders
    except sqlite3.Error as e:
        print(f"حدث خطأ في قاعدة البيانات عند جلب كل المجلدات: {e}")
        return []
    finally:
        if conn:
            conn.close()