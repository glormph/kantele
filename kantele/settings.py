# Django settings for kantele project.
import os

# local box setup
APIKEY = os.environ.get('APIKEY')
STORAGESHARE = os.environ.get('STORAGESHARE')
ANALYSIS_STORAGESHARE = os.environ.get('ANALYSIS_STORAGESHARE')
TMPSHARE = os.environ.get('TMPSHARE')

# swestore
SWESTORE_URI = os.environ.get('SWESTORE_URI')
DAV_PATH = os.environ.get('DAVPATH')
CACERTLOC = os.environ.get('CACERTLOC')
CERTLOC = os.environ.get('CERTLOC')
CERTKEYLOC = os.environ.get('CERTKEYLOC')
CERTPASS = os.environ.get('CERTPASS')

# mzml converters
PUTTYKEY = os.environ.get('PUTTYKEY')


# site infra
SWESTORECLIENT_APIKEY = os.environ.get('SWESTORECLIENT_APIKEY')
STORAGECLIENT_APIKEY = os.environ.get('STORAGECLIENT_APIKEY')
MZMLCLIENT_APIKEY = os.environ.get('MZMLCLIENT_APIKEY')
ANALYSISCLIENT_APIKEY = os.environ.get('ANALYSISCLIENT_APIKEY')
CLIENT_APIKEYS = [SWESTORECLIENT_APIKEY, STORAGECLIENT_APIKEY, MZMLCLIENT_APIKEY,
                  ANALYSISCLIENT_APIKEY]
QUEUE_STORAGE = 'mv_md5_storage'
QUEUE_SWESTORE = 'create_swestore'
QUEUE_GALAXY_STAGE = 'galaxy-stage'
QUEUE_GALAXY_TOOLS = 'galaxy-tools'
QUEUE_GALAXY_WORKFLOW = 'galaxy-workflow'

QUEUES_PWIZ = ['pwiz1', 'pwiz2']
QUEUES_PWIZOUT = {'pwiz1': 'proteowiz1_out', 'pwiz2': 'proteowiz2_out'}
PROTOCOL = 'https://'
CERTFILE = os.environ.get('KANTELECERT')
KANTELEHOST = '{}{}'.format(PROTOCOL, os.environ.get('KANTELEHOST'))
TMPSHARENAME = 'tmp'
STORAGESHARENAME = 'storage'
SHAREMAP = {TMPSHARENAME: TMPSHARE,
            STORAGESHARENAME: STORAGESHARE
            }
CELERY_BROKER_HOST = os.environ.get('RABBITHOST')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'rpc'

# qc datasets
QC_USER_ID = os.environ.get('QC_USER_ID')
QC_DATATYPE = os.environ.get('QC_DATATYPE')
QC_ORGANISM = os.environ.get('QC_ORGANISM')
INSTRUMENT_QC_PROJECT = os.environ.get('INSTRUMENT_QC_PROJECT')
INSTRUMENT_QC_EXP = os.environ.get('INSTRUMENT_QC_EXP')
INSTRUMENT_QC_RUNNAME = os.environ.get('INSTRUMENT_QC_RUNNAME')

# galaxy
GALAXY_URL = os.environ.get('GALAXY_URL')
GALAXY_ADMIN_APIKEY = os.environ.get('GALAXY_ADMIN_APIKEY')

# nextflow
NEXTFLOW_RUNDIR = os.environ.get('NEXTFLOW_RUNDIR')

# django
ALLOWED_HOSTS = [os.environ.get('KANTELEHOST')]
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = True
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#CSRF_COOKIE_SECURE = False
#SESSION_COOKIE_SECURE = True
#X_FRAME_OPTIONS = 'DENY'
#SECURE_CONTENT_TYPE_NOSNIFF = True
#SECURE_BROWSER_XSS_FILTER = False


# Application definition

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
APPEND_SLASH = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'home.apps.HomeConfig',
    'datasets.apps.DatasetsConfig',
    'rawstatus.apps.RawstatusConfig',
    'jobs.apps.JobsConfig',
    'corefac.apps.CorefacConfig',
    'analysis.apps.AnalysisConfig',
    'dashboard.apps.DashboardConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kantele.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [(os.path.join(BASE_DIR, 'templates')), ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'kantele.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'kanteledb',
        'USER': 'kanteleuser',
        'PASSWORD': os.environ.get('DB_PASS'),
        'HOST': '127.0.0.1',
        'PORT': 5432,
        'ATOMIC_REQUESTS': True,
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = 'static/'
LOGIN_URL = '/login'
SESSION_COOKIE_EXPIRE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
