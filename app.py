from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
import mysql.connector
from datetime import date, datetime, timedelta
import urllib.parse
import os
import csv
import io
import json
# Import du SDK Google GenAI officiel
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = "cni_training_secret_key"

# Initialisation du client Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LBoPzylRstK6UmCnfBisKmHZdEJJjuk4xwg3wM4BgdfQ")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

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

    # Prochain cycle à venir
    cursor.execute("SELECT * FROM cycle WHERE date_deb > %s ORDER BY date_deb ASC LIMIT 1", (date.today(),))
    next_cycle = cursor.fetchone()

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
        next_cycle=next_cycle,
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

@app.route("/formateurs/edit/<path:nom_prenom>", methods=["GET", "POST"])
def edit_formateur(nom_prenom):
    nom_prenom_decoded = urllib.parse.unquote(nom_prenom)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        specialite = request.form.get("specialite", "").strip()
        direction = request.form.get("direction", "").strip()
        entreprise = request.form.get("entreprise", "").strip()
        
        # FIX: was checking undefined variable 'stroke', now correctly checks 'entreprise'
        if not specialite or not entreprise:
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

# Profil détaillé formateur
@app.route("/formateurs/profile/<path:nom_prenom>")
def formateur_profile(nom_prenom):
    nom_prenom_decoded = urllib.parse.unquote(nom_prenom)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM formateur WHERE nom_prenom = %s", (nom_prenom_decoded,))
    formateur = cursor.fetchone()
    
    if not formateur:
        flash("المكوّن غير موجود.", "danger")
        return redirect(url_for("list_formateurs"))
    
    # Historique des cycles associés
    cursor.execute("""
        SELECT * FROM cycle 
        WHERE for1 = %s OR for2 = %s OR for3 = %s 
        ORDER BY date_deb DESC
    """, (nom_prenom_decoded, nom_prenom_decoded, nom_prenom_decoded))
    cycles_history = cursor.fetchall()
    
    # Statistiques
    total_cycles = len(cycles_history)
    active_cycles = sum(1 for c in cycles_history if str(c['date_deb']) <= date.today().isoformat() <= str(c['date_fin']))
    past_cycles = sum(1 for c in cycles_history if str(c['date_fin']) < date.today().isoformat())
    
    cursor.close()
    conn.close()
    
    return render_template(
        "formateur_profile.html",
        formateur=formateur,
        cycles_history=cycles_history,
        total_cycles=total_cycles,
        active_cycles=active_cycles,
        past_cycles=past_cycles,
        today=date.today().isoformat()
    )

# Export CSV formateurs
@app.route("/formateurs/export-csv")
def export_formateurs_csv():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM formateur ORDER BY nom_prenom ASC")
    trainers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['الاسم واللقب', 'التخصص', 'الإدارة / القسم', 'المؤسسة / الشركة'])
    for t in trainers:
        writer.writerow([t['nom_prenom'], t['specialite'], t.get('direction', ''), t['entreprise']])
    
    output.seek(0)
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": f"attachment; filename=formateurs_{date.today()}.csv"}
    )

# -------------------------------------------------------------
# 3. MANAGEMENT DES CYCLES DE FORMATION (CRUD)
# -------------------------------------------------------------
@app.route("/cycles")
def list_cycles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '')
    
    query = "SELECT * FROM cycle"
    params = []
    conditions = []
    
    today = date.today().isoformat()
    if status_filter == 'active':
        conditions.append("date_deb <= %s AND date_fin >= %s")
        params.extend([today, today])
    elif status_filter == 'upcoming':
        conditions.append("date_deb > %s")
        params.append(today)
    elif status_filter == 'past':
        conditions.append("date_fin < %s")
        params.append(today)
    
    if search:
        conditions.append("(theme LIKE %s OR num_act LIKE %s OR for1 LIKE %s OR for2 LIKE %s OR for3 LIKE %s)")
        like = f"%{search}%"
        params.extend([like, like, like, like, like])
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY date_deb DESC"
    
    cursor.execute(query, params)
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
        today=date.today().isoformat(),
        status_filter=status_filter,
        search=search
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

    # Vérification conflit de salle
    cursor.execute("""
        SELECT num_act, theme FROM cycle 
        WHERE num_salle = %s AND NOT (date_fin < %s OR date_deb > %s)
    """, (num_salle, date_deb, date_fin))
    conflict = cursor.fetchone()
    if conflict:
        flash(f"تحذير: القاعة {num_salle} محجوزة بالفعل في هذه الفترة للدورة: {conflict[1]}. تم التسجيل مع الإشارة للتعارض.", "warning")
        
    try:
        cursor.execute(
            "INSERT INTO cycle (num_act, theme, date_deb, date_fin, for1, for2, for3, num_salle) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (num_act, theme, date_deb, date_fin, form_1, form_2, form_3, num_salle)
        )
        conn.commit()
        if not conflict:
            flash("تم تسجيل الدورة التكوينية بنجاح.", "success")
    except Exception as e:
        flash(f"فشل تسجيل الدورة: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("list_cycles"))

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

# Export CSV cycles
@app.route("/cycles/export-csv")
def export_cycles_csv():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cycle ORDER BY date_deb DESC")
    cycles = cursor.fetchall()
    cursor.close()
    conn.close()
    
    today = date.today().isoformat()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['رقم العملية', 'الدورة التكوينية', 'تاريخ البداية', 'تاريخ النهاية', 'مكون 1', 'مكون 2', 'مكون 3', 'القاعة', 'الحالة'])
    for c in cycles:
        if today < str(c['date_deb']):
            status = 'قادمة'
        elif today > str(c['date_fin']):
            status = 'منتهية'
        else:
            status = 'مستمرة'
        writer.writerow([
            c['num_act'], c['theme'], c['date_deb'], c['date_fin'],
            c.get('for1',''), c.get('for2',''), c.get('for3',''),
            c['num_salle'], status
        ])
    
    output.seek(0)
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": f"attachment; filename=cycles_{date.today()}.csv"}
    )

# -------------------------------------------------------------
# 4. GÉNÉRATION DE PLAN (IA)
# -------------------------------------------------------------
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
    
    # Calcul durée
    try:
        d1 = datetime.strptime(str(cycle['date_deb']), '%Y-%m-%d')
        d2 = datetime.strptime(str(cycle['date_fin']), '%Y-%m-%d')
        nb_jours = (d2 - d1).days + 1
    except:
        nb_jours = 5
    
    prompt = f"""
    En tant qu'expert en ingénierie de formation pour le CNI (Centre National de l'Informatique de Tunisie), 
    génère un plan de formation professionnel et détaillé pour le thème suivant : "{cycle['theme']}".
    La formation dure {nb_jours} jours.
    Le plan doit être rédigé en arabe, structuré et clair, contenant :
    1. الأهداف العامة والخاصة للدورة
    2. تفصيل المحتوى يوماً بيوم أو وحدة بوحدة
    3. المنهجية والأساليب البيداغوجية المقترحة
    4. الوسائل والأدوات التكنولوجية المطلوبة
    5. الكفاءات المكتسبة في نهاية الدورة
    6. طرق التقييم والمتابعة
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

    return render_template("view_plan.html", cycle=cycle, plan_content=plan_content, nb_jours=nb_jours)

# -------------------------------------------------------------
# 5. API ROUTES (JSON)
# -------------------------------------------------------------

# Chatbot IA
@app.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "Message vide"}), 400
    
    # Contexte du système CNI
    system_context = """
    أنت مساعد ذكاء اصطناعي متخصص للمركز الوطني للإعلامية (CNI) في تونس.
    أنت متخصص في:
    - إدارة الدورات التكوينية والتدريبية
    - إرشاد المستخدمين حول نظام إدارة التكوين
    - تقديم نصائح حول بيداغوجيا التدريب في مجال الإعلامية
    - الإجابة عن أسئلة تتعلق بتقنيات المعلومات والتكوين المهني
    أجب دائماً بالعربية بأسلوب مهني ومختصر وواضح.
    إذا سُئلت عن شيء خارج نطاق اختصاصك، قل ذلك بأدب.
    """
    
    prompt = f"{system_context}\n\nالمستخدم: {user_message}\n\nالمساعد:"
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        reply = response.text
    except Exception as e:
        reply = f"عذراً، حدث خطأ أثناء معالجة طلبك: {str(e)}"
    
    return jsonify({"reply": reply})

# Génération QCM
@app.route("/api/ai-quiz/<path:num_act>")
def ai_quiz(num_act):
    num_act_decoded = urllib.parse.unquote(num_act)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cycle WHERE num_act = %s", (num_act_decoded,))
    cycle = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not cycle:
        return jsonify({"error": "Cycle non trouvé"}), 404
    
    prompt = f"""
    أنت خبير في التكوين المهني في مجال الإعلامية.
    أنشئ 5 أسئلة اختيار من متعدد (QCM) تقييمية للدورة التكوينية حول موضوع: "{cycle['theme']}".
    
    أرجع النتيجة بصيغة JSON فقط، بدون أي نص إضافي، بالتنسيق التالي:
    {{
      "questions": [
        {{
          "id": 1,
          "question": "نص السؤال",
          "options": ["الخيار أ", "الخيار ب", "الخيار ج", "الخيار د"],
          "correct": 0,
          "explanation": "شرح الإجابة الصحيحة"
        }}
      ]
    }}
    
    تأكد أن:
    - الأسئلة متنوعة (فهم، تطبيق، تحليل)
    - الخيارات واضحة ومتمايزة
    - الإجابة الصحيحة مرقمة من 0 إلى 3
    """
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        raw_text = response.text.strip()
        # Nettoyage du JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()
        quiz_data = json.loads(raw_text)
        return jsonify(quiz_data)
    except Exception as e:
        return jsonify({"error": f"خطأ في توليد الأسئلة: {str(e)}"}), 500

# Statistiques pour graphiques
@app.route("/api/stats")
def api_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today = date.today().isoformat()
    
    # Cycles par mois (12 derniers mois)
    cursor.execute("""
        SELECT DATE_FORMAT(date_deb, '%Y-%m') as month, COUNT(*) as count
        FROM cycle
        WHERE date_deb >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY month
        ORDER BY month ASC
    """)
    monthly_data = cursor.fetchall()
    
    # Répartition par statut
    cursor.execute("SELECT COUNT(*) as count FROM cycle WHERE date_deb <= %s AND date_fin >= %s", (today, today))
    active_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM cycle WHERE date_deb > %s", (today,))
    upcoming_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM cycle WHERE date_fin < %s", (today,))
    past_count = cursor.fetchone()['count']
    
    # Top formateurs
    cursor.execute("""
        SELECT f.nom_prenom, f.specialite,
               COUNT(c.num_act) as nb_cycles
        FROM formateur f
        LEFT JOIN cycle c ON (c.for1 = f.nom_prenom OR c.for2 = f.nom_prenom OR c.for3 = f.nom_prenom)
        GROUP BY f.nom_prenom, f.specialite
        ORDER BY nb_cycles DESC
        LIMIT 5
    """)
    top_formateurs = cursor.fetchall()
    
    # Répartition par salle
    cursor.execute("""
        SELECT num_salle, COUNT(*) as count
        FROM cycle
        GROUP BY num_salle
        ORDER BY count DESC
        LIMIT 10
    """)
    room_stats = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        "monthly": [{"month": r['month'], "count": r['count']} for r in monthly_data],
        "status": {
            "active": active_count,
            "upcoming": upcoming_count,
            "past": past_count
        },
        "top_formateurs": [
            {"name": r['nom_prenom'], "specialite": r['specialite'], "count": r['nb_cycles']}
            for r in top_formateurs
        ],
        "room_stats": [
            {"room": f"قاعة {r['num_salle']}", "count": r['count']}
            for r in room_stats
        ]
    })

# Vérification conflit de salle
@app.route("/api/check-conflict")
def check_conflict():
    num_salle = request.args.get("num_salle", "")
    date_deb = request.args.get("date_deb", "")
    date_fin = request.args.get("date_fin", "")
    exclude_num_act = request.args.get("exclude", "")
    
    if not num_salle or not date_deb or not date_fin:
        return jsonify({"conflict": False})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT num_act, theme, date_deb, date_fin FROM cycle 
        WHERE num_salle = %s AND NOT (date_fin < %s OR date_deb > %s)
    """
    params = [num_salle, date_deb, date_fin]
    
    if exclude_num_act:
        query += " AND num_act != %s"
        params.append(exclude_num_act)
    
    cursor.execute(query, params)
    conflict = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if conflict:
        return jsonify({
            "conflict": True,
            "message": f"القاعة {num_salle} محجوزة للدورة: {conflict['theme']} من {conflict['date_deb']} إلى {conflict['date_fin']}"
        })
    
    return jsonify({"conflict": False})

# -------------------------------------------------------------
# 6. PAGE ANALYTICS
# -------------------------------------------------------------
@app.route("/analytics")
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    today = date.today().isoformat()
    
    cursor.execute("SELECT COUNT(*) AS total FROM cycle")
    total_cycles = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) AS total FROM formateur")
    total_formateurs = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) AS total FROM cycle WHERE date_deb <= %s AND date_fin >= %s", (today, today))
    active_cycles = cursor.fetchone()['total']
    
    # Cycle le plus long
    cursor.execute("""
        SELECT theme, DATEDIFF(date_fin, date_deb)+1 as duree
        FROM cycle ORDER BY duree DESC LIMIT 1
    """)
    longest_cycle = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return render_template("analytics.html",
        total_cycles=total_cycles,
        total_formateurs=total_formateurs,
        active_cycles=active_cycles,
        longest_cycle=longest_cycle,
        today=today
    )

# -------------------------------------------------------------
# 7. PAGE CALENDRIER
# -------------------------------------------------------------
@app.route("/calendar")
def calendar_view():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cycle ORDER BY date_deb ASC")
    cycles = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Préparer les événements pour le calendrier JS
    events = []
    today = date.today().isoformat()
    for c in cycles:
        deb = str(c['date_deb'])
        fin = str(c['date_fin'])
        if today < deb:
            color = '#3b82f6'  # bleu = à venir
        elif today > fin:
            color = '#6b7280'  # gris = passé
        else:
            color = '#10b981'  # vert = en cours
        
        events.append({
            "title": c['theme'],
            "start": deb,
            "end": fin,
            "color": color,
            "num_act": c['num_act'],
            "num_salle": c['num_salle'],
            "for1": c.get('for1', ''),
            "for2": c.get('for2', ''),
            "for3": c.get('for3', ''),
        })
    
    return render_template("calendar.html", events=json.dumps(events, ensure_ascii=False))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)