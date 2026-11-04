import os
import numpy as np
import pandas as pd

def generate_student_dataset(n_samples=4000, random_seed=42, output_path='student_performance_data.csv'):
    """
    Generate realistic student performance data modeling academic GPA forecasting.
    
    Features:
      - attendance: Percentage of attended classes (0–100%)
      - study_hours: Dedicated weekly study hours (0–20 hrs)
      - past_cgpa: Cumulative Grade Point Average prior to current semester (0.0–4.0 scale)
      - quiz_performance: Average score on regular quizzes (0–100%)
      - class_participation: Classroom engagement rating (1–10 scale)
      
    Target:
      - final_gpa: End-of-semester final GPA (0.0–4.0 continuous scale)
    """
    np.random.seed(random_seed)

    # Latent academic ability / engagement factor modeled via Beta distribution
    ability = np.random.beta(5, 3, size=n_samples)

    # Realistic feature distributions aligned with student academic records
    attendance = np.clip(ability * 80 + np.random.normal(15, 10, n_samples), 10, 100)
    study_hours = np.clip(ability * 16 + np.random.normal(3, 2.5, n_samples), 0, 20)
    past_cgpa = np.clip(ability * 3.2 + np.random.normal(0.7, 0.35, n_samples), 0.5, 4.0)
    quiz_performance = np.clip(ability * 75 + np.random.normal(20, 10, n_samples), 15, 100)
    class_participation = np.clip(np.round(ability * 8 + np.random.normal(1.5, 1.2, n_samples)), 1, 10)

    # Academic weights grounded in educational research:
    # Prior CGPA is the anchor predictor (~38%), quiz mastery is direct coursework signal (~26%),
    # weekly study effort (~18%), regular attendance (~11%), class engagement (~7%).
    w_cgpa = 0.38
    w_quiz = 0.26
    w_study = 0.18
    w_att = 0.11
    w_part = 0.07

    norm_score = (
        w_cgpa * (past_cgpa / 4.0) +
        w_quiz * (quiz_performance / 100.0) +
        w_study * (study_hours / 20.0) +
        w_att * (attendance / 100.0) +
        w_part * (class_participation / 10.0)
    )

    # Realistic performance variance (sigma = 0.03 GPA points)
    final_gpa = np.clip(norm_score * 4.0 + np.random.normal(0, 0.03, n_samples), 0.0, 4.0)

    df = pd.DataFrame({
        'attendance': np.round(attendance, 1),
        'study_hours': np.round(study_hours, 1),
        'past_cgpa': np.round(past_cgpa, 2),
        'quiz_performance': np.round(quiz_performance, 1),
        'class_participation': class_participation.astype(int),
        'final_gpa': np.round(final_gpa, 2)
    })

    # Introduce realistic missing values (~4% per feature) to validate imputer pipeline robustness
    for col in ['attendance', 'study_hours', 'past_cgpa', 'quiz_performance', 'class_participation']:
        mask = np.random.rand(n_samples) < 0.04
        df.loc[mask, col] = np.nan

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} student records saved to '{output_path}'.")
    return df

if __name__ == '__main__':
    generate_student_dataset(output_path='student_performance_data.csv')
