#!/bin/bash
# Bootstrap script for local development

echo "AI Powered Modeling and Optimisation of Distributed Oxygen & Energy Intelligence System for Climate Resilient Healthcare"
echo "============================================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate || . venv/Scripts/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo "✓ Dependencies installed"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please update .env with your database credentials"
fi

echo ""
echo "Bootstrap complete! Next steps:"
echo "1. Update .env with your PostgreSQL credentials"
echo "2. Create database: createdb oxygen_pred"
echo "3. Start API: uvicorn app.main:app --reload"
echo "4. View docs: http://localhost:8000/docs"
