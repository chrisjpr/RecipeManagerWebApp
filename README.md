# RecipeManagerWebApp

A Django-powered web application for managing, sharing, and organizing recipes with AI-enhanced features.

## Features

### Recipe Management
- Create, edit, and delete recipes with ingredients and step-by-step instructions
- Multiple recipe import methods:
  - **URL scraping** - Extract recipes from cooking websites
  - **Image upload** - AI-powered recipe extraction from photos
  - **Text input** - Parse recipes from copied text
- Export recipes to PDF format
- Background removal for recipe images

### Social Features
- User accounts with customizable profile icons
- Friend system with request/accept workflow
- Recipe visibility controls (Private, Friends, Public)
- Browse and copy recipes from friends and public collection

### Smart Features
- Background job processing for resource-intensive tasks
- Mobile-responsive design with user-agent detection
- AWS S3 integration for scalable media storage

## Tech Stack

- **Framework**: Django 5.2.4
- **Database**: PostgreSQL (Supabase/RDS compatible)
- **AI**: OpenAI API for image and text processing
- **Storage**: AWS S3 via django-storages
- **Background Jobs**: Django-RQ with Redis
- **Web Scraping**: recipe-scrapers, BeautifulSoup4
- **Image Processing**: Pillow, rembg, OpenCV
- **PDF Generation**: xhtml2pdf, PyPDF2, PyMuPDF

## Setup

### Prerequisites
- Python 3.x
- PostgreSQL database
- Redis (for background jobs)
- AWS S3 bucket (for media storage)
- OpenAI API key

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd RecipeManagerWebApp


