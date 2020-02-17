# Django settings for kantele project.
import os

# local box setup
APIKEY = os.environ.get('APIKEY')
STORAGESHARE = os.environ.get('STORAGESHARE')
ANALYSISSHARE = os.environ.get('ANALYSISSHARE')
TMPSHARE = os.environ.get('TMPSHARE')

# swestore
SWESTORE_URI = os.environ.get('SWESTORE_URI')
DAV_PATH = os.environ.get('DAVPATH')
CACERTLOC = os.environ.get('CACERTLOC')
CERTLOC = os.environ.get('CERTLOC')
CERTKEYLOC = os.environ.get('CERTKEYLOC')
CERTPASS = os.environ.get('CERTPASS')

DSM_DIR = os.environ.get('DSM_DIR')

# mzml converters
PUTTYKEY = os.environ.get('PUTTYKEY')


# site infra
SWESTORECLIENT_APIKEY = os.environ.get('SWESTORECLIENT_APIKEY')
STORAGECLIENT_APIKEY = os.environ.get('STORAGECLIENT_APIKEY')
MZMLCLIENT_APIKEY = os.environ.get('MZMLCLIENT_APIKEY')
ANALYSISCLIENT_APIKEY = os.environ.get('ANALYSISCLIENT_APIKEY')
ADMIN_APIKEY = os.environ.get('ADMIN_APIKEY')
CLIENT_APIKEYS = [SWESTORECLIENT_APIKEY, STORAGECLIENT_APIKEY, MZMLCLIENT_APIKEY,
                  ANALYSISCLIENT_APIKEY, ADMIN_APIKEY]
QUEUE_STORAGE = 'mv_md5_storage'
QUEUE_PXDOWNLOAD = 'pxdownload'
QUEUE_SWESTORE = 'create_swestore'
QUEUE_PDC = 'pdc_archive'
QUEUE_NXF = 'nextflow'
QUEUE_QC_NXF = 'qc_nextflow'

QUEUES_PWIZ = ['pwiz1', 'pwiz2']
QUEUE_QCPWIZ = 'pwiz_qc'
QUEUES_PWIZOUT = {'pwiz1': 'proteowiz1_out', 'pwiz2': 'proteowiz2_out', 'pwiz_qc': 'proteowiz2_out'}
PROTOCOL = 'https://'
CERTFILE = os.environ.get('KANTELECERT')
KANTELEHOST = '{}{}'.format(PROTOCOL, os.environ.get('KANTELEHOST'))
TMPSHARENAME = 'tmp'
STORAGESHARENAME = 'storage'
ANALYSISSHARENAME = 'analysis'

TMP_STORAGE_KEYFILE = os.environ.get('STORAGE_KEYFILE')
STORAGE_USER = os.environ.get('STORAGE_USER')
STORAGE_HOST = os.environ.get('STORAGE_HOST')
TMP_SCP_PATH = '{}@{}:{}'.format(STORAGE_USER, STORAGE_HOST, TMPSHARE)

SHAREMAP = {TMPSHARENAME: TMPSHARE,
            STORAGESHARENAME: STORAGESHARE,
            ANALYSISSHARENAME: ANALYSISSHARE,
            }
NGINX_ANALYSIS_REDIRECT = '/analysisfiles'
SERVABLE_FILENAMES = ['qc.html', 'qc_full.html', 'qc_light.html', 'pipeline_report.html']

SLACK_BASE = 'https://hooks.slack.com/services/'
SLACK_WORKSPACE = os.environ.get('SLACK_WORKSPACE')
SLACK_HOOKS = {k.replace('SLACK_HOOK_', ''): v for k,v in os.environ.items() if k.startswith('SLACK_HOOK_')}
# message queue
RABBIT_HOST = os.environ.get('RABBITHOST')
RABBIT_USER = 'kantele'
RABBIT_VHOST = 'kantele_vhost'
RABBIT_PASSWORD = os.environ.get('AMQPASS')
CELERY_BROKER_URL = 'amqp://{}:{}@{}:5672/{}'.format(RABBIT_USER, RABBIT_PASSWORD, RABBIT_HOST, RABBIT_VHOST)
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'rpc'

# datatypes
try:
    RAW_SFGROUP_ID = int(os.environ.get('RAW_SF_GROUP_ID'))
    BRUKER_SFGROUP_ID = int(os.environ.get('BRUKER_SF_GROUP_ID'))
    MZML_SFGROUP_ID = int(os.environ.get('MZML_SF_GROUP_ID'))
    REFINEDMZML_SFGROUP_ID = int(os.environ.get('REFINED_SF_GROUP_ID'))
    FILE_ISDIR_SFGROUPS = [BRUKER_SFGROUP_ID]
    SECONDARY_FTYPES = [MZML_SFGROUP_ID, REFINEDMZML_SFGROUP_ID]
except TypeError:
    # Tasks have no notion of these IDs so they will error
    pass

ANALYSISOUT_FTID = int(os.environ.get('ANALYSISOUT_FTID'))
DATABASE_FTID = int(os.environ.get('DATABASE_FTID'))

# Lifespan for mzMLs and Instrument-QC RAW files, in days
MAX_MZML_STORAGE_TIME_POST_ANALYSIS = int(os.environ.get('MAX_MZML_STORAGE_TIME_POST_ANALYSIS'))
MAX_MZML_LC_STORAGE_TIME = int(os.environ.get('MAX_MZML_LC_STORAGE_TIME'))
MAX_MZML_QC_STORAGE_TIME = int(os.environ.get('MAX_MZML_QC_STORAGE_TIME'))

# Labelcheck experiment name
LCEXPNAME = '__labelchecks'
LC_DTYPE_ID = int(os.environ.get('LC_DTYPE_ID'))

# local datasets
LOCAL_PTYPE_ID = int(os.environ.get('LOCAL_PTYPE_ID'))

# external datasets
ENSEMBL_API = 'https://rest.ensembl.org/info/software'
# human, canonical/isoform, only swiss
UNIPROT_API = 'https://www.uniprot.org/uniprot/?query=organism:9606+AND+reviewed:yes&format=fasta'
ENSEMBL_DL_URL = 'ftp://ftp.ensembl.org/pub/release-{}/fasta/homo_sapiens/pep/'
BIOMART_URL = 'https://ensembl.org/biomart/martservice'
PX_PROJECT_ID = os.environ.get('PX_PROJECT_ID')
EXTERNAL_PRODUCER_ID = os.environ.get('EXTERNAL_PRODUCER_ID')
UPLOADDIR = 'uploadfiles'

# qc datasets
QC_USER_ID = os.environ.get('QC_USER_ID')
QC_DATATYPE = os.environ.get('QC_DATATYPE')
QC_ORGANISM = os.environ.get('QC_ORGANISM')
INSTRUMENT_QC_PROJECT = os.environ.get('INSTRUMENT_QC_PROJECT')
INSTRUMENT_QC_EXP = os.environ.get('INSTRUMENT_QC_EXP')
INSTRUMENT_QC_RUNNAME = os.environ.get('INSTRUMENT_QC_RUNNAME')

# nextflow
LIBRARY_FILE_PATH = 'databases'
ANALYSIS_STAGESHARE = os.environ.get('STAGESHARE')
SMALL_NFRUNDIR = os.environ.get('NEXTFLOW_RUNDIR')
LARGER_NFRUNDIR = os.environ.get('LARGER_NFRUNDIR')
NF_RUNDIRS = {'small': SMALL_NFRUNDIR,
              'larger': LARGER_NFRUNDIR,
            }
LONGQC_NXF_WF_ID = os.environ.get('LONGQC_WFID')
LONGQC_FADB_ID = os.environ.get('LONGQC_DBID')
MZREFINER_NXFWFV_ID = os.environ.get('REFINE_MZML_WFVID')
MZREFINER_FADB_ID = os.environ.get('REFINE_MZML_DBID')
NXF_VER = os.environ.get('NXF_VER')

# django
ALLOWED_HOSTS = [os.environ.get('KANTELEHOST').split(':')[0]]
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
