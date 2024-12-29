from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
from setup_database import setup_database
from dateutil.relativedelta import relativedelta


app = Flask(__name__)
app.secret_key = '123'
DATABASE = 'workshop.db'
UPLOAD_FOLDER = 'static/uploads/workshop_photos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER





def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Custom filter for adding months to a date
@app.template_filter('date_add')
def date_add(date_str, months=1):
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        new_date = date + relativedelta(months=months)
        return new_date.strftime('%Y-%m-%d')
    except ValueError:
        return "Invalid Date"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # To return results as dictionaries
    return conn

@app.route('/')
def index():
    if not os.path.exists(DATABASE):
        setup_database()

    # Get the current month as a number (e.g., "01" for January)
    current_month = datetime.now().strftime('%Y-%m')
    current_month_number = datetime.now().strftime('%m')  # Example: "01" for January

    conn = sqlite3.connect('workshop.db')
    conn.row_factory = sqlite3.Row

    # Fetch monthly metrics
    monthly_metrics = conn.execute('''
        SELECT 
            -- Total income for the current month
            (SELECT ROUND(SUM(Amount), 2)
             FROM Payments
             WHERE strftime('%Y-%m', PaymentDate) = ?) AS total_income_month,

            -- Outstanding balances for the current month
            (SELECT ROUND(SUM(CostOnCustomer) - 
                    COALESCE((SELECT SUM(Amount)
                              FROM Payments p
                              WHERE p.WorkshopID = w.WorkshopID), 0), 2)
             FROM Workshop w
             WHERE strftime('%Y-%m', RequestDate) = ?) AS total_outstanding_month,

            -- Total workshops for the current month
            (SELECT COUNT(*)
             FROM Workshop
             WHERE strftime('%Y-%m', RequestDate) = ?) AS total_workshops_month,

            -- Completed workshops for the current month
            (SELECT COUNT(*)
             FROM Workshop
             WHERE Status = 'تم الانتهاء' AND strftime('%Y-%m', RequestDate) = ?) AS completed_workshops_month
    ''', (current_month, current_month, current_month, current_month)).fetchone()

    # Fetch overall metrics
    overall_metrics = conn.execute('''
        SELECT 
            (SELECT COUNT(*) FROM Workshop) AS total_workshops,
            (SELECT COUNT(*) FROM Workshop WHERE Status = 'تم الانتهاء') AS completed_workshops,
            (SELECT COUNT(*) FROM Workshop WHERE Status = 'قيد العمل') AS pending_workshops,
            (SELECT COUNT(*) FROM Workshop WHERE Status = 'قيد التحقق') AS confirmation_workshops,
            (SELECT ROUND(SUM(CostOnCustomer) - 
                    COALESCE((SELECT SUM(Amount)
                              FROM Payments p
                              WHERE p.WorkshopID = w.WorkshopID), 0), 2)
             FROM Workshop w
             WHERE (CostOnCustomer - 
                    COALESCE((SELECT SUM(Amount) 
                              FROM Payments p 
                              WHERE p.WorkshopID = w.WorkshopID), 0)) > 0) AS total_outstanding
    ''').fetchone()

    # Handle potential None values
    metrics = {
        "total_income_month": monthly_metrics["total_income_month"] or 0,
        "total_outstanding_month": monthly_metrics["total_outstanding_month"] or 0,
        "total_workshops_month": monthly_metrics["total_workshops_month"] or 0,
        "completed_workshops_month": monthly_metrics["completed_workshops_month"] or 0,
        "total_workshops": overall_metrics["total_workshops"] or 0,
        "completed_workshops": overall_metrics["completed_workshops"] or 0,
        "pending_workshops": overall_metrics["pending_workshops"] or 0,
        "confirmation_workshops": overall_metrics["confirmation_workshops"] or 0,
        "total_outstanding": overall_metrics["total_outstanding"] or 0,
    }

    # Format metrics to remove decimals if they are integers
    formatted_metrics = {
        key: (int(value) if value == int(value) else value) for key, value in metrics.items()
    }

    # Add the current month number to metrics
    formatted_metrics['current_month_number'] = int(current_month_number)

    conn.close()
    return render_template('index.html', metrics=formatted_metrics)

@app.route('/add_workshop', methods=['GET', 'POST'])
def add_workshop():
    if request.method == 'POST':
        try:
            # Retrieve form data
            location = request.form.get('location')
            customer_name = request.form.get('customer_name')
            phone_number = request.form.get('phone_number')
            details = request.form.get('details')
            request_date = request.form.get('request_date') or None
            cost_on_me = float(request.form.get('cost_on_me') or 0.0)
            cost_on_customer = float(request.form.get('cost_on_customer') or 0.0)
            status = request.form.get('status') or 'قيد العمل'
            includes_rails = request.form.get('includes_rails', 'لا')
            worker_ids = request.form.getlist('worker_ids')
            workshop_types = request.form.getlist('workshop_types')

            # Create the workshop
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Workshop (Location, CustomerName, PhoneNumber, Details, RequestDate, CostOnMe, CostOnCustomer, Status, IncludesRails)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (location, customer_name, phone_number, details, request_date, cost_on_me, cost_on_customer, status, includes_rails))
            workshop_id = cursor.lastrowid

            # Insert workers
            for worker_id in worker_ids:
                cursor.execute('''
                    INSERT INTO WorkshopWorkers (WorkshopID, WorkerID)
                    VALUES (?, ?)
                ''', (workshop_id, worker_id))

            # Insert types
            for workshop_type in workshop_types:
                cursor.execute('''
                    INSERT INTO WorkshopTypes (WorkshopID, Type)
                    VALUES (?, ?)
                ''', (workshop_id, workshop_type))

            # Handle photo uploads
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])


            print(request.form)
            photos = request.files.getlist('photos')
            print(photos)
            captions = request.form.getlist('captions')
            print(captions)
            for photo, caption in zip(photos, captions):
                if photo and allowed_file(photo.filename):
                    filename = secure_filename(photo.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'{workshop_id}_{filename}')
                    photo.save(filepath)

                    # Save the photo details in the database
                    cursor.execute('''
                        INSERT INTO WorkshopPhotos (WorkshopID, PhotoPath, Caption)
                        VALUES (?, ?, ?)
                    ''', (workshop_id, filepath, caption))

            conn.commit()
            conn.close()
            flash('تمت إضافة الورشة بنجاح!', 'success')
            return redirect(url_for('workshops'))
        except Exception as e:
            conn.rollback()
            flash(f'حدث خطأ أثناء إضافة الورشة: {str(e)}', 'danger')
        finally:
            conn.close()

    conn = get_db_connection()
    workers = conn.execute('SELECT WorkerID, Name FROM Workers').fetchall()
    conn.close()
    return render_template('add_workshop.html', workers=workers)

@app.route('/workshops')
def workshops():
    conn = get_db_connection()

    # Fetch workshops and calculate outstanding balances
    workshops = conn.execute('''
        SELECT 
            w.WorkshopID, 
            w.Location, 
            w.CustomerName, 
            w.CostOnCustomer, 
            w.Status, 
            w.RequestDate, 
            w.Notes,
            IFNULL(SUM(p.Amount), 0) AS TotalPayments, 
            (w.CostOnCustomer - IFNULL(SUM(p.Amount), 0)) AS OutstandingBalance
        FROM Workshop w
        LEFT JOIN Payments p ON w.WorkshopID = p.WorkshopID
        GROUP BY w.WorkshopID
    ''').fetchall()

    conn.close()
    return render_template('workshops.html', workshops=workshops)

@app.route('/workshop/<int:workshop_id>')
def workshop_details(workshop_id):
    conn = get_db_connection()
    workshop = conn.execute('SELECT * FROM Workshop WHERE WorkshopID = ?', (workshop_id,)).fetchone()
    conn.close()

    if workshop is None:
        flash('Workshop not found!', 'error')
        return redirect(url_for('workshops'))

    return render_template('workshop_details.html', workshop=workshop)

@app.route('/edit_workshop/<int:workshop_id>', methods=['GET', 'POST'])
def edit_workshop(workshop_id):
    conn = get_db_connection()

    if request.method == 'POST':
        location = request.form.get('location')
        customer_name = request.form.get('customer_name')
        phone_number = request.form.get('phone_number')
        details = request.form.get('details')
        workshop_type = request.form.get('type')
        worker_id = request.form.get('worker_id')
        request_date = request.form.get('request_date')
        cost_on_me = request.form.get('cost_on_me')
        cost_on_customer = request.form.get('cost_on_customer')
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        includes_rails = request.form.get('includes_rails', 'لا')  # Default to 'لا'

        conn.execute('''
            UPDATE Workshop
            SET Location = ?, CustomerName = ?, PhoneNumber = ?, Details = ?, Type = ?, WorkerID = ?, 
                RequestDate = ?, CostOnMe = ?, CostOnCustomer = ?, Status = ?, Notes = ?, IncludesRails = ?
            WHERE WorkshopID = ?
        ''', (location, customer_name, phone_number, details, workshop_type, worker_id, request_date, cost_on_me, cost_on_customer, status, notes, includes_rails, workshop_id))
        conn.commit()
        conn.close()

        flash('تم تعديل الورشة بنجاح!', 'success')
        return redirect(url_for('workshops'))

    workshop = conn.execute('SELECT * FROM Workshop WHERE WorkshopID = ?', (workshop_id,)).fetchone()
    workers = conn.execute('SELECT WorkerID, Name FROM Workers').fetchall()
    conn.close()
    return render_template('edit_workshop.html', workshop=workshop, workers=workers)

@app.route('/workshop/payments/<int:workshop_id>', methods=['GET', 'POST'])
def manage_payments(workshop_id):
    conn = get_db_connection()
    if request.method == 'POST':
        payment_date = request.form['payment_date']
        amount = float(request.form['amount'])
        notes = request.form.get('payment_notes', '').strip()  # Get payment notes, default to empty

        # Validate that total payments do not exceed the cost
        total_payments = conn.execute('''
            SELECT IFNULL(SUM(Amount), 0)
            FROM Payments
            WHERE WorkshopID = ?
        ''', (workshop_id,)).fetchone()[0]
        
        workshop = conn.execute('''
            SELECT CostOnCustomer
            FROM Workshop
            WHERE WorkshopID = ?
        ''', (workshop_id,)).fetchone()

        if not workshop:
            flash('الورشة غير موجودة', 'error')
            return redirect(url_for('workshops'))

        remaining_balance = workshop['CostOnCustomer'] - total_payments
        if amount > remaining_balance:
            flash('المبلغ المدخل يتجاوز المبلغ المطلوب!', 'error')
            return redirect(url_for('manage_payments', workshop_id=workshop_id))

        # Insert the payment with notes
        conn.execute('''
            INSERT INTO Payments (WorkshopID, PaymentDate, Amount, Notes)
            VALUES (?, ?, ?, ?)
        ''', (workshop_id, payment_date, amount, notes))
        conn.commit()
        flash('تم إضافة الدفعة والملاحظات بنجاح', 'success')
        return redirect(url_for('manage_payments', workshop_id=workshop_id))

    # Fetch workshop and payments
    workshop = conn.execute('''
        SELECT w.WorkshopID, w.CostOnCustomer, IFNULL(SUM(p.Amount), 0) AS TotalPayments
        FROM Workshop w
        LEFT JOIN Payments p ON w.WorkshopID = p.WorkshopID
        WHERE w.WorkshopID = ?
    ''', (workshop_id,)).fetchone()
    payments = conn.execute('''
        SELECT p.PaymentDate, p.Amount, p.Notes
        FROM Payments p
        WHERE p.WorkshopID = ?
    ''', (workshop_id,)).fetchall()
    conn.close()

    if not workshop:
        flash('الورشة غير موجودة', 'error')
        return redirect(url_for('workshops'))

    return render_template('payments.html', workshop=workshop, payments=payments)

@app.route('/view_workshop/<int:workshop_id>')
def view_workshop(workshop_id):
    conn = get_db_connection()

    # Fetch workshop details
    workshop = conn.execute('SELECT * FROM Workshop WHERE WorkshopID = ?', (workshop_id,)).fetchone()
    if not workshop:
        conn.close()
        flash('الورشة غير موجودة', 'error')
        return redirect(url_for('workshops'))

    # Fetch associated workers
    workers = conn.execute('''
        SELECT w.Name 
        FROM WorkshopWorkers ww
        JOIN Workers w ON ww.WorkerID = w.WorkerID
        WHERE ww.WorkshopID = ?
    ''', (workshop_id,)).fetchall()

    # Fetch associated types
    types = conn.execute('SELECT Type FROM WorkshopTypes WHERE WorkshopID = ?', (workshop_id,)).fetchall()

    # Fetch associated photos
    photos = conn.execute('SELECT PhotoPath, Caption FROM WorkshopPhotos WHERE WorkshopID = ?', (workshop_id,)).fetchall()

    conn.close()

    # Convert results into lists for easier rendering
    worker_names = [worker['Name'] for worker in workers]
    workshop_types = [type['Type'] for type in types]

    return render_template(
        'view_workshop.html',
        workshop=workshop,
        worker_names=worker_names,
        workshop_types=workshop_types,
        photos=photos
    )

@app.route('/workers')
def workers():
    conn = get_db_connection()
    workers = conn.execute('SELECT * FROM Workers').fetchall()
    conn.close()
    return render_template('workers.html', workers=workers)

@app.route('/add_worker', methods=['GET', 'POST'])
def add_worker():
    if request.method == 'POST':
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        role = request.form.get('role')
        salary = request.form.get('salary')
        start_date = request.form.get('start_date')

        if not name or not role or not salary or not start_date:
            flash('All fields are required!', 'error')
            return redirect(url_for('add_worker'))

        conn = get_db_connection()
        conn.execute('INSERT INTO Workers (Name, PhoneNumber, Role, Salary, StartDate) VALUES (?, ?, ?, ?, ?)',
                     (name, phone_number, role, salary, start_date))
        conn.commit()
        conn.close()
        flash('Worker added successfully!', 'success')
        return redirect(url_for('workers'))
    return render_template('add_worker.html')

@app.route('/edit_worker/<int:worker_id>', methods=['GET', 'POST'])
def edit_worker(worker_id):
    conn = get_db_connection()
    worker = conn.execute('SELECT * FROM Workers WHERE WorkerID = ?', (worker_id,)).fetchone()

    if not worker:
        conn.close()
        flash('Worker not found!', 'error')
        return redirect(url_for('workers'))

    if request.method == 'POST':
        # Get updated details from the form
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        role = request.form.get('role')
        salary = request.form.get('salary')
        start_date = request.form.get('start_date')

        # Validate required fields
        if not name or not role or not salary or not start_date:
            flash('All fields are required!', 'error')
            conn.close()
            return redirect(url_for('edit_worker', worker_id=worker_id))

        # Update worker details in the database
        conn.execute('''
            UPDATE Workers
            SET Name = ?, PhoneNumber = ?, Role = ?, Salary = ?, StartDate = ?
            WHERE WorkerID = ?
        ''', (name, phone_number, role, salary, start_date, worker_id))
        conn.commit()
        conn.close()

        flash('Worker updated successfully!', 'success')
        return redirect(url_for('workers'))

    conn.close()
    return render_template('edit_worker.html', worker=worker)

@app.route('/delete_worker/<int:worker_id>', methods=['POST'])
def delete_worker(worker_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM Workers WHERE WorkerID = ?', (worker_id,))
    conn.commit()
    conn.close()
    flash('Worker deleted successfully!', 'success')
    return redirect(url_for('workers'))

@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    conn = get_db_connection()

    # Fetch optional filters from the request
    filter_date = request.args.get('filter_date', None)  # Allow empty date
    transaction_type = request.args.get('transaction_type', '')
    search_query = request.args.get('search', '').strip().lower()  # Search query

    # Build the query dynamically based on filters
    query = 'SELECT * FROM Transactions WHERE 1=1'
    params = []

    if filter_date:
        query += ' AND Date = ?'
        params.append(filter_date)

    if transaction_type:
        query += ' AND TransactionType = ?'
        params.append(transaction_type)

    transactions = conn.execute(query, params).fetchall()

    # Apply search query
    if search_query:
        transactions = [t for t in transactions if search_query in t['Notes'].lower() or search_query in t['Category'].lower()]

    # Calculate totals dynamically for the displayed results
    total_in = sum(t['Amount'] for t in transactions if t['Amount'] > 0)
    total_out = abs(sum(t['Amount'] for t in transactions if t['Amount'] < 0))
    net_balance = total_in - total_out

    conn.close()

    return render_template(
        'transactions.html',
        transactions=transactions,
        filter_date=filter_date,
        transaction_type=transaction_type,
        search_query=search_query,
        total_in=int(total_in) if total_in == int(total_in) else total_in,
        total_out=int(total_out) if total_out == int(total_out) else total_out,
        net_balance=int(net_balance) if net_balance == int(net_balance) else net_balance
    )

@app.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        transaction_type = request.form['transaction_type']
        amount = float(request.form['amount'])
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = request.form['category']
        notes = request.form['notes']

        # Insert transaction into the database
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO Transactions (TransactionType, Amount, Date, Category, Notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (transaction_type, amount, date, category, notes))
        conn.commit()
        conn.close()

        flash('تمت إضافة المعاملة بنجاح!', 'success')
        return redirect(url_for('transactions'))

    return render_template('add_transaction.html')

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        print("Database not found. Please run setup_database.py first.")
    app.run(debug=True)
