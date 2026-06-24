from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from datetime import date
import urllib.parse
import os
# Import du SDK Google GenAI officiel
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = "cni_training_secret_key"

# Initialisation du client Gemini API via la variable d'environnement GEMINI_API_KEY
ai_client = genai.Client(api_key="AQ.Ab8RN6LBoPzylRstK6UmCnfBisKmHZdEJJjuk4xwg3wM4BgdfQ")
# Configuration de la connexion à la base de données
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="bd_arabe",
        charset="utf8mb4",
        use_unicode=True
    )

# -------------------------------------------------------------
# 1. ACCUEIL / TABLEAU DE BORD
# -------------------------------------------------------------
@app.route("/")
@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) AS total FROM cycle")
    total_cycles = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) AS total FROM formateur")
    total_formateurs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(DISTINCT num_salle) AS total FROM cycle WHERE date_fin >= %s", (date.today(),))
    active_rooms = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) AS total FROM cycle WHERE date_fin >= %s", (date.today(),))
    active_cycles = cursor.fetchone()['total']
    
    cursor.execute("SELECT * FROM cycle ORDER BY date_deb DESC LIMIT 5")
    recent_cycles = cursor.fetchall()
    
    cursor.execute("SELECT * FROM formateur LIMIT 5")
    recent_formateurs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template(
        "dashboard.html",
        total_cycles=total_cycles,
        total_formateurs=total_formateurs,
        active_rooms=active_rooms,
        active_cycles=active_cycles,
        recent_cycles=recent_cycles,
        recent_formateurs=recent_formateurs,
        today=date.today().isoformat()
    )

# -------------------------------------------------------------
# 2. MANAGEMENT DES FORMATEURS (CRUD)
# -------------------------------------------------------------
@app.route("/formateurs")
def list_formateurs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM formateur ORDER BY nom_prenom ASC")
    trainers = cursor.fetchall()
    total_trainers = len(trainers)
    cursor.close()
    conn.close()
    return render_template("formateur.html", trainers=trainers, total_trainers=total_trainers)

@app.route("/formateurs/add", methods=["POST"])
def add_formateur():
    nom_prenom = request.form.get("nom_prenom", "").strip()
    specialite = request.form.get("specialite", "").strip()
    direction = request.form.get("direction", "").strip()
    entreprise = request.form.get("entreprise", "").strip()
    
    if not nom_prenom or not specialite or not entreprise:
        flash("يرجى ملء الحقول الإجبارية.", "warning")
        return redirect(url_for("list_formateurs"))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nom_prenom FROM formateur WHERE nom_prenom = %s", (nom_prenom,))
    if cursor.fetchone():
        flash("هذا المكوّن مسجل بالفعل في قاعدة البيانات.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("list_formateurs"))
        
    try:
        cursor.execute(
            "INSERT INTO formateur (nom_prenom, specialite, direction, entreprise) VALUES (%s, %s, %s, %s)",
            (nom_prenom, specialite, direction, entreprise)
        )
        conn.commit()
        flash("تمت إضافة المكوّن بنجاح.", "success")
    except Exception as e:
        flash(f"فشلت عملية الإضافة: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("list_formateurs"))

# استخدام <path:...> هنا لحماية الأسماء التي تحتوي على رموز
@app.route("/formateurs/edit/<path:nom_prenom>", methods=["GET", "POST"])
def edit_formateur(nom_prenom):
    nom_prenom_decoded = urllib.parse.unquote(nom_prenom)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        specialite = request.form.get("specialite", "").strip()
        direction = request.form.get("direction", "").strip()
        entreprise = request.form.get("entreprise", "").strip()
        
        if not specialite or not stroke:
            flash("يرجى ملء جميع الحقول الإجبارية.", "danger")
        else:
            try:
                cursor.execute(
                    "UPDATE formateur SET specialite = %s, direction = %s, entreprise = %s WHERE nom_prenom = %s",
                    (specialite, direction, entreprise, nom_prenom_decoded)
                )
                conn.commit()
                flash("تم تحديث بيانات المكوّن بنجاح.", "success")
                cursor.close()
                conn.close()
                return redirect(url_for("list_formateurs"))
            except Exception as e:
                flash(f"حدث خطأ أثناء التحديث: {str(e)}", "danger")
                
    cursor.execute("SELECT * FROM formateur WHERE nom_prenom = %s", (nom_prenom_decoded,))
    formateur = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not formateur:
        flash("المكوّن غير موجود.", "danger")
        return redirect(url_for("list_formateurs"))
        
    return render_template("edit_formateur.html", formateur=formateur)

@app.route("/formateurs/delete/<path:nom_prenom>")
def delete_formateur(nom_prenom):
    nom_prenom_decoded = urllib.parse.unquote(nom_prenom)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT COUNT(*) AS count FROM cycle WHERE for1 = %s OR for2 = %s OR for3 = %s",
        (nom_prenom_decoded, nom_prenom_decoded, nom_prenom_decoded)
    )
    if cursor.fetchone()[0] > 0:
        flash("لا يمكن حذف المكوّن لأنه مرتبط بدورة تكوينية نشطة أو سابقة.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("list_formateurs"))
        
    try:
        cursor.execute("DELETE FROM formateur WHERE nom_prenom = %s", (nom_prenom_decoded,))
        conn.commit()
        flash("تم حذف المكوّن بنجاح.", "success")
    except Exception as e:
        flash(f"فشلت عملية الحذف: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("list_formateurs"))

# -------------------------------------------------------------
# 3. MANAGEMENT DES CYCLES DE FORMATION (CRUD)
# -------------------------------------------------------------
@app.route("/cycles")
def list_cycles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM cycle ORDER BY date_deb DESC")
    cycles = cursor.fetchall()
    total_cycles = len(cycles)
    
    cursor.execute("SELECT nom_prenom FROM formateur ORDER BY nom_prenom ASC")
    formateurs = [row['nom_prenom'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template(
        "cycle.html", 
        cycles=cycles, 
        total_cycles=total_cycles, 
        formateurs=formateurs,
        today=date.today().isoformat()
    )

@app.route("/cycles/add", methods=["POST"])
def add_cycle():
    num_act = request.form.get("num_act", "").strip()
    theme = request.form.get("theme", "").strip()
    date_deb = request.form.get("date_deb", "").strip()
    date_fin = request.form.get("date_fin", "").strip()
    form_1 = request.form.get("form_1", "").strip()
    form_2 = request.form.get("form_2", "").strip()
    form_3 = request.form.get("form_3", "").strip()
    num_salle = request.form.get("num_salle", "").strip()
    
    if not num_act or not theme or not date_deb or not date_fin or not num_salle:
        flash("يرجى ملء كافة الحقول الإجبارية.", "warning")
        return redirect(url_for("list_cycles"))
        
    if date_fin < date_deb:
        flash("فشل تسجيل الدورة: تاريخ النهاية لا يمكن أن يسبق تاريخ البداية.", "danger")
        return redirect(url_for("list_cycles"))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT num_act FROM cycle WHERE num_act = %s", (num_act,))
    if cursor.fetchone():
        flash("رقم العملية هذا مسجل بالفعل لدورة أخرى.", "warning")
        cursor.close()
        conn.close()
        return redirect(url_for("list_cycles"))
        
    try:
        cursor.execute(
            "INSERT INTO cycle (num_act, theme, date_deb, date_fin, for1, for2, for3, num_salle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (num_act, theme, date_deb, date_fin, form_1, form_2, form_3, num_salle)
        )
        conn.commit()
        flash("تم تسجيل الدورة التكوينية بنجاح.", "success")
    except Exception as e:
        flash(f"فشل تسجيل الدورة: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("list_cycles"))

# تم التعديل إلى <path:num_act> للسماح برمز الـ / في رقم العملية عند التعديل
@app.route("/cycles/edit/<path:num_act>", methods=["GET", "POST"])
def edit_cycle(num_act):
    num_act_decoded = urllib.parse.unquote(num_act)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        theme = request.form.get("theme", "").strip()
        date_deb = request.form.get("date_deb", "").strip()
        date_fin = request.form.get("date_fin", "").strip()
        form_1 = request.form.get("form_1", "").strip()
        form_2 = request.form.get("form_2", "").strip()
        form_3 = request.form.get("form_3", "").strip()
        num_salle = request.form.get("num_salle", "").strip()
        
        if not theme or not date_deb or not date_fin or not num_salle:
            flash("يرجى ملء جميع الحقول الإجبارية.", "danger")
        elif date_fin < date_deb:
            flash("تاريخ نهاية الدورة لا يمكن أن يسبق تاريخ بدايتها.", "danger")
        else:
            try:
                cursor.execute(
                    "UPDATE cycle SET theme = %s, date_deb = %s, date_fin = %s, for1 = %s, for2 = %s, for3 = %s, num_salle = %s WHERE num_act = %s",
                    (theme, date_deb, date_fin, form_1, form_2, form_3, num_salle, num_act_decoded)
                )
                conn.commit()
                flash("تم تحديث بيانات الدورة التكوينية بنجاح.", "success")
                cursor.close()
                conn.close()
                return redirect(url_for("list_cycles"))
            except Exception as e:
                flash(f"حدث خطأ أثناء التحديث: {str(e)}", "danger")
                
    cursor.execute("SELECT * FROM cycle WHERE num_act = %s", (num_act_decoded,))
    cycle = cursor.fetchone()
    
    cursor.execute("SELECT nom_prenom FROM formateur ORDER BY nom_prenom ASC")
    formateurs = [row['nom_prenom'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    if not cycle:
        flash("الدورة التكوينية غير موجودة.", "danger")
        return redirect(url_for("list_cycles"))
        
    return render_template("edit_cycle.html", cycle=cycle, formateurs=formateurs)

# تم التعديل إلى <path:num_act> هنا أيضاً للحذف الآمن
@app.route("/cycles/delete/<path:num_act>")
def delete_cycle(num_act):
    num_act_decoded = urllib.parse.unquote(num_act)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM cycle WHERE num_act = %s", (num_act_decoded,))
        conn.commit()
        flash("تم حذف الدورة التكوينية بنجاح.", "success")
    except Exception as e:
        flash(f"فشلت عملية الحذف: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("list_cycles"))

# -------------------------------------------------------------
# 4. INTÉGRATION IA (GÉNÉRATION DE PROGRAMME DE FORMATION)
# -------------------------------------------------------------
# تعديل المسار الحرج هنا بإضافة <path:num_act> لحل مشكلة الـ 404 نهائياً
@app.route("/cycles/generate_plan/<path:num_act>")
def generate_plan(num_act):
    num_act_decoded = urllib.parse.unquote(num_act)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM cycle WHERE num_act = %s", (num_act_decoded,))
    cycle = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not cycle:
        flash("الدورة التكوينية غير موجودة.", "danger")
        return redirect(url_for("list_cycles"))
    
    prompt = f"""
    En tant qu'expert en ingénierie de formation pour le CNI (Centre National de l'Informatique), 
    gène un plan de formation professionnel et détaillé pour le thème suivant : "{cycle['theme']}".
    Le plan doit être rédigé en arabe de préférence, structuré et clair, contenant :
    1. Les objectifs principaux de la formation.
    2. Un découpage par jours ou par modules.
    3. Les compétences acquises à la fin.
    Réponds directement avec le plan bien formaté en Markdown.
    """
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        plan_content = response.text
    except Exception as e:
        plan_content = f"خطأ أثناء الاتصال بالذكاء الاصطناعي: {str(e)}"

    return render_template("view_plan.html", cycle=cycle, plan_content=plan_content)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)