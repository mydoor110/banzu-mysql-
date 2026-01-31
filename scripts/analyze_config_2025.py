
import os
import sys
import json
import pymysql
from datetime import datetime, date
from collections import defaultdict
import importlib.util

# Add project root to path
sys.path.append(os.getcwd())

from models.database import get_db
from config.settings import DatabaseConfig
from blueprints.safety import extract_score_from_assessment
from blueprints.personnel import (
    calculate_performance_score_monthly,
    calculate_performance_score_period,
    calculate_safety_score_dual_track,
    calculate_training_score_with_penalty,
    calculate_learning_ability_monthly,
    # calculate_learning_ability_longterm # This seems complex to simulate without correct input structure, 
    # but I can simulate monthly which is easier.
)

# Mock Flask app and DB connection if needed, or just use pymysql directly
def connect_db():
    return pymysql.connect(
        host=DatabaseConfig.MYSQL_HOST,
        port=DatabaseConfig.MYSQL_PORT,
        user=DatabaseConfig.MYSQL_USER,
        password=DatabaseConfig.MYSQL_PASSWORD,
        database=DatabaseConfig.MYSQL_DATABASE,
        charset=DatabaseConfig.MYSQL_CHARSET,
        cursorclass=pymysql.cursors.DictCursor
    )

def load_config(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT config_data FROM algorithm_active_config WHERE id = 1")
        row = cur.fetchone()
        if row:
            return json.loads(row['config_data'])
    return {}

def fetch_data(conn):
    start_date = '2025-01-01'
    end_date = '2025-11-30'
    
    data = {
        'employees': [],
        'safety': [],
        'training': [],
        'performance': []
    }
    
    with conn.cursor() as cur:
        # Employees
        cur.execute("SELECT emp_no, name, entry_date, certification_date FROM employees")
        data['employees'] = cur.fetchall()
        
        # Safety (Jan-Nov)
        cur.execute("""
            SELECT inspected_person, inspection_date, assessment, category
            FROM safety_inspection_records 
            WHERE inspection_date >= %s AND inspection_date <= %s
        """, (start_date, end_date))
        data['safety'] = cur.fetchall()
        
        # Training (Jan-Nov)
        cur.execute("""
            SELECT emp_no, training_date, score, is_qualified, is_disqualified
            FROM training_records
            WHERE training_date >= %s AND training_date <= %s
        """, (start_date, end_date))
        data['training'] = cur.fetchall()
        
        # Performance (Jan-Nov)
        cur.execute("""
            SELECT emp_no, year, month, grade, score
            FROM performance_records
            WHERE year = 2025 AND month >= 1 AND month <= 11
        """)
        data['performance'] = cur.fetchall()
        
    return data

def analyze_safety(data, config):
    print("\n=== Safety Analysis (Jan-Nov 2025) ===")
    records = data['safety']
    
    # Group by person
    person_violations = defaultdict(list)
    for r in records:
        if not r['inspected_person']: continue
        score_val = extract_score_from_assessment(r['assessment'])
        if score_val > 0:
            person_violations[r['inspected_person']].append(score_val)
            
    # Calculate scores
    scores = []
    high_freq_penalties = 0
    severity_penalties = 0
    critical_violations = 0
    
    critical_threshold = config['safety']['severity_track']['critical_threshold']
    
    for person, violations in person_violations.items():
        res = calculate_safety_score_dual_track(violations, 11, config) # 11 months
        scores.append(res['final_score'])
        
        if res['score_a'] < 100: high_freq_penalties += 1
        if res['score_b'] < 100: severity_penalties += 1
        
        for v in violations:
            if v >= critical_threshold:
                critical_violations += 1
                break
                
    total_people = len(data['employees'])  # Assuming we analyze all employees or just those with violations?
    # Better to analyze those with violations for impact, but overall population matters for frequency.
    # Actually, people with NO violations have score 100.
    
    people_with_violations = len(person_violations)
    people_with_100 = total_people - people_with_violations # Roughly
    
    # Add 100 scores for others
    scores.extend([100] * people_with_100)
    
    avg_score = sum(scores) / len(scores) if scores else 0
    min_score = min(scores) if scores else 0
    
    print(f"Total Employees: {total_people}")
    print(f"Employees with Violations: {people_with_violations}")
    print(f"Average Score: {avg_score:.2f}")
    print(f"Min Score: {min_score:.2f}")
    print(f"People penalized for Frequency (Score A < 100): {high_freq_penalties}")
    print(f"People penalized for Severity (Score B < 100): {severity_penalties}")
    print(f"People with Critical Violations (>= {critical_threshold}): {critical_violations}")
    
    # Distribution
    dist = defaultdict(int)
    for s in scores:
        if s >= 95: dist['95-100'] += 1
        elif s >= 80: dist['80-95'] += 1
        elif s >= 60: dist['60-80'] += 1
        else: dist['<60'] += 1
        
    print("Score Distribution:")
    for k, v in sorted(dist.items()):
        print(f"  {k}: {v} ({v/total_people*100:.1f}%)")

def analyze_training(data, config):
    print("\n=== Training Analysis (Jan-Nov 2025) ===")
    records = data['training']
    employees = {e['emp_no']: e for e in data['employees']}
    
    person_records = defaultdict(list)
    for r in records:
        person_records[r['emp_no']].append(r)
        
    scores = []
    penalized_count = 0
    absolute_fails = 0
    afr_penalties = 0
    
    for emp_no, recs in person_records.items():
        emp = employees.get(emp_no)
        cert_years = 2.0 # Default experienced
        if emp and emp['certification_date']:
            try:
                # Simple approx
                c_date = datetime.strptime(str(emp['certification_date']), '%Y-%m-%d')
                cert_years = (datetime(2025, 11, 30) - c_date).days / 365.0
            except:
                pass
                
        # Calculate
        res = calculate_training_score_with_penalty(recs, duration_days=334, cert_years=cert_years, config=config)
        scores.append(res['radar_score'])
        
        if res['penalty_coefficient'] < 1.0:
            penalized_count += 1
            if '绝对失格' in res['risk_alert']['text']:
                absolute_fails += 1
            elif '年化' in res['risk_alert']['text']:
                afr_penalties += 1
                
    total_active = len(person_records) # Only count those who had training?
    # Or should we include those with 0 training?
    # Logic handles 0 training as long/mid term absence. We can skip that for now and focus on penalty rules.
    
    if not scores:
        print("No training records found.")
        return

    avg_score = sum(scores) / len(scores)
    
    print(f"Employees with Training Records: {total_active}")
    print(f"Average Score: {avg_score:.2f}")
    print(f"Employees Penalized: {penalized_count} ({penalized_count/total_active*100:.1f}%)")
    print(f"  Due to Absolute Fail Threshold: {absolute_fails}")
    print(f"  Due to Annualized Failure Rate (AFR): {afr_penalties}")
    
    # AFR Analysis
    # Let's see actual AFRs
    afrs = []
    for emp_no, recs in person_records.items():
        fail_count = sum(1 for r in recs if r['is_disqualified'] or r['score']==0 or r['is_qualified']==0)
        afr = (fail_count / 334) * 365
        if fail_count > 0:
            afrs.append(afr)
            
    if afrs:
        print(f"Max AFR detected: {max(afrs):.2f}")
        print(f"Avg AFR (for those with fails): {sum(afrs)/len(afrs):.2f}")

def analyze_performance(data, config):
    print("\n=== Performance Analysis (Jan-Nov 2025) ===")
    records = data['performance']
    
    grade_counts = defaultdict(int)
    total_records = len(records)
    
    person_grades = defaultdict(list)
    for r in records:
        g = r['grade'].upper() if r['grade'] else 'B+'
        grade_counts[g] += 1
        person_grades[r['emp_no']].append(g)
        
    print(f"Total Performance Records: {total_records}")
    print("Grade Distribution:")
    for g, c in sorted(grade_counts.items()):
        print(f"  {g}: {c} ({c/total_records*100:.1f}%)")
        
    # Check Contamination Rules (D/C counts)
    d_threshold = config['performance']['contamination_rules']['d_count_threshold']
    c_threshold = config['performance']['contamination_rules']['c_count_threshold']
    
    people_hit_d_limit = 0
    people_hit_c_limit = 0
    
    for emp_no, grades in person_grades.items():
        d_count = grades.count('D')
        c_count = grades.count('C')
        
        if d_count >= d_threshold:
            people_hit_d_limit += 1
        if c_count >= c_threshold:
            people_hit_c_limit += 1
            
    print(f"People hitting D-count limit (>= {d_threshold}): {people_hit_d_limit}")
    print(f"People hitting C-count limit (>= {c_threshold}): {people_hit_c_limit}")

def analyze_learning(data, config):
    print("\n=== Learning Ability Analysis (Simulation) ===")
    # Simulate monthly learning scores
    # We need comprehensive scores for each month
    # Comp = Perf * Wp + Safety * Ws + Training * Wt
    
    weights = config['comprehensive']['score_weights']
    
    # Build monthly cache
    monthly_data = defaultdict(lambda: defaultdict(dict)) # emp -> month -> type -> score
    
    # 1. Performance
    for r in data['performance']:
        m_str = f"{r['year']}-{r['month']:02d}"
        monthly_data[r['emp_no']][m_str]['perf'] = float(r['score'] or 95)
        
    # 2. Safety (Monthly)
    # This is harder, need to bin violations by month
    violations_by_emp_month = defaultdict(lambda: defaultdict(list))
    for r in data['safety']:
        if not r['inspected_person']: continue
        m_str = r['inspection_date'].strftime('%Y-%m') if hasattr(r['inspection_date'], 'strftime') else str(r['inspection_date'])[:7]
        score_val = extract_score_from_assessment(r['assessment'])
        if score_val > 0:
            violations_by_emp_month[r['inspected_person']][m_str].append(score_val)
            
    for emp in monthly_data: # Iterate emps we know from performance (likely active)
        # Use employee name mapping?
        # Assuming for now name match or we use employees list to map emp_no <-> name
        pass 
    
    # Need name map
    emp_map = {e['emp_no']: e['name'] for e in data['employees']}
    name_map = {e['name']: e['emp_no'] for e in data['employees']}
    
    # Fill Safety
    for name, month_vs in violations_by_emp_month.items():
        emp_no = name_map.get(name)
        if not emp_no: continue
        for m_str, vs in month_vs.items():
            res = calculate_safety_score_dual_track(vs, 1, config)
            monthly_data[emp_no][m_str]['safety'] = res['final_score']
            
    # Fill Training (Monthly)
    # Similar binning
    train_by_emp_month = defaultdict(lambda: defaultdict(list))
    for r in data['training']:
        m_str = r['training_date'].strftime('%Y-%m') if hasattr(r['training_date'], 'strftime') else str(r['training_date'])[:7]
        train_by_emp_month[r['emp_no']][m_str].append(r)
        
    for emp_no, month_recs in train_by_emp_month.items():
        for m_str, recs in month_recs.items():
            res = calculate_training_score_with_penalty(recs, duration_days=30, config=config)
            monthly_data[emp_no][m_str]['train'] = res['radar_score']
            
    # Calculate Comp scores
    comp_scores = defaultdict(dict)
    months = [f"2025-{i:02d}" for i in range(1, 12)]
    
    for emp_no in monthly_data:
        for m in months:
            d = monthly_data[emp_no][m]
            p = d.get('perf', 95.0) # Default B+
            s = d.get('safety', 100.0)
            t = d.get('train', 90.0) # Default training score? Or use accumulation?
            
            comp = p * weights['performance'] + s * weights['safety'] + t * weights['training']
            comp_scores[emp_no][m] = comp
            
    # Now simulate Learning Ability (Month over Month)
    tiers = defaultdict(int)
    deltas = []
    
    for emp_no, m_scores in comp_scores.items():
        sorted_months = sorted(m_scores.keys())
        for i in range(1, len(sorted_months)):
            curr = m_scores[sorted_months[i]]
            prev = m_scores[sorted_months[i-1]]
            
            res = calculate_learning_ability_monthly(curr, prev)
            tiers[res['tier']] += 1
            deltas.append(res['delta'])
            
    total_months_calc = len(deltas)
    print(f"Total Monthly Transitions Calculated: {total_months_calc}")
    print("Learning Tier Distribution:")
    for t, c in sorted(tiers.items()):
        print(f"  {t}: {c} ({c/total_months_calc*100:.1f}%)")
        
    print(f"Average Delta: {sum(deltas)/len(deltas):.2f}")


def main():
    conn = connect_db()
    try:
        config = load_config(conn)
        print(f"Loaded Config based on preset: {config.get('based_on_preset', 'Unknown')}")
        
        data = fetch_data(conn)
        
        analyze_safety(data, config)
        analyze_training(data, config)
        analyze_performance(data, config)
        analyze_learning(data, config)
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
