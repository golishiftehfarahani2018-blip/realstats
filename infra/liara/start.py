"""Single HTTP app for a separate Liara demo; database/media remain external."""
import os
import signal
import subprocess
import sys
import time
import uuid


def main():
    required = ['ESTATE_INSTALLATION_ID','DJANGO_SECRET_KEY','FIELD_ENCRYPTION_KEY','POSTGRES_DB','POSTGRES_USER',
                'POSTGRES_PASSWORD','POSTGRES_HOST','ALLOWED_HOSTS','CSRF_TRUSTED_ORIGINS',
                'S3_ENDPOINT','S3_ACCESS_KEY','S3_SECRET_KEY','S3_PRIVATE_BUCKET','S3_PUBLIC_BUCKET']
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print('Required configuration missing: '+', '.join(missing),file=sys.stderr)
        return 1
    if os.environ.get('DEBUG') != '0':
        print('This deployment requires DEBUG=0.',file=sys.stderr)
        return 1
    if not os.environ['S3_ENDPOINT'].startswith('https://'):
        print('Use an HTTPS endpoint for external object storage.',file=sys.stderr)
        return 1
    if any(not origin.strip().startswith('https://') for origin in os.environ['CSRF_TRUSTED_ORIGINS'].split(',')):
        print('Public origins must use HTTPS.',file=sys.stderr)
        return 1
    # Refuse to migrate a pre-existing unrelated database. A persistent identifier
    # ties this new application to its dedicated database across redeployments.
    try:
        installation=str(uuid.UUID(os.environ['ESTATE_INSTALLATION_ID']))
    except ValueError:
        print('ESTATE_INSTALLATION_ID must be a persistent UUID for this new demo.',file=sys.stderr)
        return 1
    import psycopg
    try:
        connection=psycopg.connect(dbname=os.environ['POSTGRES_DB'],user=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'],host=os.environ['POSTGRES_HOST'],
            port=os.getenv('POSTGRES_PORT','5432'),autocommit=True,connect_timeout=10)
    except psycopg.Error:
        print('Cannot connect to the dedicated demo database.',file=sys.stderr)
        return 1
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(873246019)')
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            tables={row[0] for row in cursor.fetchall()}
            if 'estate_deployment_marker' in tables:
                cursor.execute('SELECT installation FROM estate_deployment_marker')
                markers=cursor.fetchall()
                if markers!=[(installation,)]:
                    print('Refusing to use a database assigned to another installation.',file=sys.stderr)
                    return 1
            elif tables:
                print('Refusing to migrate a nonempty database without this demo installation marker.',file=sys.stderr)
                return 1
            else:
                cursor.execute('CREATE TABLE estate_deployment_marker (installation text PRIMARY KEY)')
                cursor.execute('INSERT INTO estate_deployment_marker (installation) VALUES (%s)',(installation,))
            result=subprocess.run(['python','manage.py','migrate','--noinput'],cwd='/app/backend')
            if result.returncode:return result.returncode
    finally:
        connection.close()  # releases the startup advisory lock
    result=subprocess.run(['python','manage.py','init_storage'],cwd='/app/backend')
    if result.returncode:return result.returncode
    children=[]
    stopping=False
    def stop(_signum=None,_frame=None):
        nonlocal stopping
        stopping=True
        for child in children:
            if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        children.append(subprocess.Popen(['gunicorn','config.wsgi:application','--bind','127.0.0.1:8000','--workers','2','--access-logfile','/dev/null'],cwd='/app/backend'))
        env=os.environ.copy();env.update(HOSTNAME='127.0.0.1',PORT='3000')
        children.append(subprocess.Popen(['node','server.js'],cwd='/app/frontend',env=env))
        children.append(subprocess.Popen(['python','manage.py','run_reminders'],cwd='/app/backend'))
        children.append(subprocess.Popen(['nginx','-g','daemon off;']))
        while not stopping:
            failed=next((child for child in children if child.poll() is not None),None)
            if failed is not None:
                print('A required application process exited; restarting the container is required.',file=sys.stderr)
                return 1
            time.sleep(1)
        return 0
    finally:
        stop()
        deadline=time.monotonic()+8
        for child in children:
            try:child.wait(timeout=max(0.1,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':sys.exit(main())
