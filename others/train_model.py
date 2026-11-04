import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

def train_and_evaluate_model():
    # Resolve dataset path whether run from root or others/
    csv_paths = ['student_performance_data.csv', 'others/student_performance_data.csv', '../others/student_performance_data.csv']
    data_path = next((p for p in csv_paths if os.path.exists(p)), None)
    if not data_path:
        raise FileNotFoundError("Could not locate 'student_performance_data.csv'.")

    print(f"Loading dataset from: {data_path}")
    data = pd.read_csv(data_path)

    features = ['attendance', 'study_hours', 'past_cgpa', 'quiz_performance', 'class_participation']
    target = 'final_gpa'

    # Filter any corrupted rows where target is missing
    data = data.dropna(subset=[target])

    X = data[features]
    y = data[target]

    print(f"Total dataset shape: {X.shape[0]} rows, {X.shape[1]} features.")
    print("Feature summary statistics:")
    print(X.describe().round(2))

    # Split dataset: 80% train, 20% test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Scikit-learn Pipeline ensuring strictly ordered preprocessing
    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='mean')),
        ('scaler', MinMaxScaler()),
        ('model', RandomForestRegressor(
            n_estimators=120,
            max_depth=16,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ))
    ])

    print("\nTraining RandomForestRegressor pipeline...")
    pipeline.fit(X_train, y_train)

    # Evaluation on Train and Test
    train_pred = pipeline.predict(X_train)
    test_pred = pipeline.predict(X_test)

    train_r2 = r2_score(y_train, train_pred)
    test_r2 = r2_score(y_test, test_pred)
    test_mae = mean_absolute_error(y_test, test_pred)
    test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))

    # 5-fold cross validation on training data
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring='r2')

    print("\n" + "="*50)
    print("MODEL EVALUATION RESULTS")
    print("="*50)
    print(f"5-Fold CV R2 Score:   {cv_scores.mean() * 100:.2f}% (+/- {cv_scores.std() * 100:.2f}%)")
    print(f"Training R2 Score:    {train_r2 * 100:.2f}%")
    print(f"Testing R2 Score:     {test_r2 * 100:.2f}%")
    print(f"Testing MAE:          {test_mae:.4f} GPA points")
    print(f"Testing RMSE:         {test_rmse:.4f} GPA points")
    print("="*50)

    # Validate predictions across key academic tiers
    print("\nValidating predictions across academic tiers:")
    benchmarks = [
        ('Near Perfect (Honors)', [98, 19, 3.95, 96, 10]),
        ('High Performer',        [90, 15, 3.50, 88, 8]),
        ('Solid Above Average',   [85, 12, 3.20, 80, 7]),
        ('Typical Average',       [80, 10, 2.90, 75, 7]),
        ('Borderline Passing',    [60, 5,  2.20, 55, 4]),
        ('Struggling Student',    [45, 3,  1.80, 45, 3]),
        ('At-Risk Student',       [25, 1,  1.20, 25, 1])
    ]

    for label, vals in benchmarks:
        pred = float(np.clip(pipeline.predict(pd.DataFrame([vals], columns=features))[0], 0, 4))
        standing = (
            'Excellent' if pred >= 3.5 else
            'Great' if pred >= 3.0 else
            'Satisfactory' if pred >= 2.5 else
            'Passing' if pred >= 2.0 else
            'At risk'
        )
        print(f"  {label:24s} -> Predicted GPA: {pred:.2f} [{standing}]")

    # Save trained model to project models/ and local folder
    output_locations = ['models/final_gpa_model.pkl', 'final_gpa_model.pkl']
    for loc in output_locations:
        dir_name = os.path.dirname(loc)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        joblib.dump(pipeline, loc)
        print(f"Model saved successfully to: {loc}")

    return pipeline

if __name__ == '__main__':
    train_and_evaluate_model()
