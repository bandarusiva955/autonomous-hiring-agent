

# Project Overview

Autonomous AI Hiring Agent is an intelligent recruitment assistant designed to automate resume analysis and candidate evaluation using machine learning and graph-based talent intelligence.

The system simulates a modern **AI-powered Applicant Tracking System (ATS)** while extending its capabilities with skill gap analysis, learning recommendations, and interview preparation support.

Users can upload resumes in **PDF or DOCX format**, and the system automatically extracts relevant information, identifies candidate skills, matches candidates with suitable job roles, and generates a complete hiring evaluation report.

This project demonstrates how **Artificial Intelligence, Natural Language Processing, and Graph-based modeling** can be used to support data-driven recruitment and career development.

---

# Key Features

### Resume Upload and Parsing

Supports PDF and DOCX resumes and extracts raw text for analysis.

### Skill Extraction

Identifies technical and professional skills using a global skills dataset.

### Job Matching

Uses **TF-IDF vectorization** and **Cosine Similarity** to match candidates with relevant job roles.

### Graph-Based Talent Analysis

Builds a **candidate–skill–job relationship graph** using NetworkX to model talent relationships.

### Skill Gap Detection

Detects missing skills required for specific job roles.

### Learning Recommendation System

Suggests learning resources based on missing skills.

### Interview Question Generator

Generates interview questions tailored to detected candidate skills.

### Candidate Evaluation Report

Produces a structured hiring report including skill match score, missing skills, and recommendations.

---

# System Architecture

```
Resume Upload
      │
      ▼
Resume Parsing
      │
      ▼
Skill Extraction
      │
      ▼
TF-IDF Feature Vectorization
      │
      ▼
Cosine Similarity Matching
      │
      ▼
Candidate–Job Graph Analysis
      │
      ▼
Skill Gap Detection
      │
      ▼
Learning Recommendation
      │
      ▼
Interview Question Generation
      │
      ▼
Final Hiring Evaluation Report
```

---

# Technology Stack

**Programming Language**

Python

**Framework**

Flask

**Machine Learning**

scikit-learn
TF-IDF Vectorization
Cosine Similarity

**Graph Analysis**

NetworkX

**Resume Parsing**

PyPDF2
python-docx

**Frontend**

HTML
CSS

**Data Storage**

JSON datasets

---

# Project Structure

```
ai-hiring-agent/

app.py
config.py
resume_parser.py
requirements.txt

data/
skills_master.json
jobs.json
learning_resources.json

engine/
pipeline.py
skill_extractor.py
resume_matcher.py
hiring_scorer.py
graph_builder.py

learning/
recommender.py

report/
report_generator.py

models/
coding_evaluator.py

templates/
index.html
report.html
```

---

# Installation

Clone the repository

git clone https://github.com/yourusername/ai-hiring-agent.git

Navigate to the project folder

cd ai-hiring-agent

Install dependencies

pip install -r requirements.txt

Run the application

python app.py

Open the application in your browser:

http://localhost:5000

---

# Demo

## Resume Upload Interface

Users can upload resumes in **PDF or DOCX format** for automated analysis.

## Candidate Evaluation Report

The system generates a detailed report including:

Detected skills
Best matching job role
Similarity score
Hiring recommendation
Skill gaps
Learning recommendations
Interview questions

## Graph-Based Talent Analysis

The system builds a **candidate–skill–job graph** to represent relationships between candidates, skills, and job roles.

---

# Example Output

Candidate Name: John Doe

Detected Skills
Python
Machine Learning
SQL
TensorFlow

Best Matching Role
Machine Learning Engineer

Match Score
0.83

Hiring Decision
Strong Hire

Missing Skills
Docker
Kubernetes

Recommended Learning
Docker Certification Course
Kubernetes Fundamentals

Suggested Interview Questions

Explain gradient descent
What is overfitting in machine learning?

---

# Use Cases

AI-powered recruitment automation
Resume analysis systems
Talent intelligence platforms
Career guidance tools
HR analytics applications

---

# Future Improvements

Semantic resume matching using sentence embeddings
Larger global skills dataset
Candidate ranking dashboard
Interactive graph visualization
Integration with job portals
Automated interview scheduling

---

# Contributing

Contributions are welcome.

If you would like to improve this project, please fork the repository and submit a pull request.

Suggestions and improvements are highly appreciated.

---

# Author

Developed as part of an Artificial Intelligence and Machine Learning project focused on building intelligent recruitment and talent analysis systems.

---

# License

This project is developed for educational and research purposes.
