"""
Main blueprint - handles the index/landing page.
"""
from flask import Blueprint, render_template

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """Landing page."""
    return render_template('index.html')
