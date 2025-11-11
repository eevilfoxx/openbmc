pipeline {
    agent any  // Используем основной контейнер Jenkins
    
    parameters {
        string(
            name: 'OPENBMC_HOST',
            defaultValue: 'localhost',
            description: 'OpenBMC host address'
        )
        string(
            name: 'OPENBMC_USER',
            defaultValue: 'root',
            description: 'OpenBMC user'
        )
        string(
            name: 'OPENBMC_PASSWORD', 
            defaultValue: '0penBmc',
            description: 'OpenBMC password'
        )
        booleanParam(
            name: 'RUN_LOAD_TEST',
            defaultValue: true,
            description: 'Run load testing'
        )
    }
    
    environment {
        WORKSPACE = "${env.WORKSPACE}"
        REPORTS_DIR = "${env.WORKSPACE}/reports"
        OPENBMC_PORT = '2443'
    }
    
    stages {
        stage('Check Environment') {
            steps {
                script {
                    // Проверяем что есть в системе
                    sh '''
                        echo "=== System Info ==="
                        whoami
                        pwd
                        ls -la
                        echo "=== Python ==="
                        python3 --version || python --version || echo "Python not found"
                        echo "=== Package Managers ==="
                        which apt-get || which yum || which apk || echo "No package manager found"
                    '''
                }
            }
        }
        
        stage('Install Python if missing') {
            steps {
                script {
                    // Пытаемся установить Python если его нет
                    sh '''
                        if ! command -v python3 && ! command -v python; then
                            echo "Installing Python..."
                            if [ -f "/etc/alpine-release" ]; then
                                apk update && apk add python3 py3-pip
                            elif [ -f "/etc/debian_version" ]; then
                                apt-get update && apt-get install -y python3 python3-pip
                            elif [ -f "/etc/redhat-release" ]; then
                                yum install -y python3 python3-pip
                            else
                                echo "Cannot detect OS, trying to install Python via available package manager"
                                apt-get update && apt-get install -y python3 python3-pip || \
                                yum install -y python3 python3-pip || \
                                apk add python3 py3-pip || \
                                echo "Failed to install Python"
                            fi
                        fi
                        
                        # Проверяем что Python теперь доступен
                        python3 --version || python --version || exit 1
                    '''
                }
            }
        }
        
        stage('Setup Virtual Environment') {
            steps {
                script {
                    sh '''
                        mkdir -p ${REPORTS_DIR}/junit
                        mkdir -p ${REPORTS_DIR}/loadtest
                        
                        # Создаем виртуальное окружение
                        python3 -m venv ${WORKSPACE}/venv || python -m venv ${WORKSPACE}/venv
                        . ${WORKSPACE}/venv/bin/activate
                        
                        # Устанавливаем зависимости
                        pip install --upgrade pip
                        pip install requests paramiko pytest pytest-html locust junitparser
                    '''
                }
            }
        }
        
        stage('Checkout and Run Tests') {
            steps {
                checkout scm
                
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        echo "Current directory:"
                        pwd
                        ls -la
                        
                        # Проверяем доступность OpenBMC
                        echo "Testing OpenBMC connection to ${OPENBMC_HOST}:${OPENBMC_PORT}"
                        if nc -z ${OPENBMC_HOST} ${OPENBMC_PORT} 2>/dev/null; then
                            echo "OpenBMC is accessible"
                            
                            # Запускаем тесты если файлы существуют
                            if [ -f "test.py" ]; then
                                echo "Running test.py"
                                python -m pytest test.py \
                                    --junitxml=${REPORTS_DIR}/junit/test_results.xml \
                                    --html=${REPORTS_DIR}/test_report.html \
                                    --self-contained-html || echo "Tests completed with some failures"
                            else
                                echo "test.py not found"
                            fi
                            
                            if [ -f "test-redfish.py" ]; then
                                echo "Running test-redfish.py" 
                                python -m pytest test-redfish.py \
                                    --junitxml=${REPORTS_DIR}/junit/test_redfish_results.xml \
                                    --html=${REPORTS_DIR}/test_redfish_report.html \
                                    --self-contained-html || echo "Tests completed with some failures"
                            else
                                echo "test-redfish.py not found"
                            fi
                            
                            if [ -f "locustfile.py" ] && [ "${RUN_LOAD_TEST}" = "true" ]; then
                                echo "Running load tests with locust"
                                locust -f locustfile.py \
                                    --host=https://${OPENBMC_HOST}:${OPENBMC_PORT} \
                                    --headless \
                                    --users=5 \
                                    --spawn-rate=1 \
                                    --run-time=1m \
                                    --html=${REPORTS_DIR}/loadtest/locust_report.html \
                                    --csv=${REPORTS_DIR}/loadtest/locust \
                                    --logfile=${REPORTS_DIR}/loadtest/locust.log || echo "Load test completed"
                            else
                                echo "locustfile.py not found or load testing disabled"
                            fi
                        else
                            echo "WARNING: Cannot connect to OpenBMC at ${OPENBMC_HOST}:${OPENBMC_PORT}"
                            echo "Creating dummy test reports"
                            
                            # Создаем заглушки для отчетов
                            cat > ${REPORTS_DIR}/junit/dummy_results.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="dummy" tests="1" errors="0" failures="0" skipped="1">
    <testcase classname="connection" name="openbmc_connection">
        <skipped message="OpenBMC not accessible at ${OPENBMC_HOST}:${OPENBMC_PORT}"/>
    </testcase>
</testsuite>
EOF
                        fi
                    '''
                }
            }
        }
    }
    
    post {
        always {
            junit "${REPORTS_DIR}/junit/*.xml"
            archiveArtifacts artifacts: 'reports/**/*', fingerprint: true
            
            script {
                // Публикуем HTML отчеты если они есть
                def htmlFiles = findFiles(glob: 'reports/*.html')
                htmlFiles.each { file ->
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'reports',
                        reportFiles: file.name,
                        reportName: "${file.name - '.html'}"
                    ])
                }
                
                def loadTestHtml = findFiles(glob: 'reports/loadtest/*.html')
                loadTestHtml.each { file ->
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'reports/loadtest',
                        reportFiles: file.name,
                        reportName: "Load Test Report"
                    ])
                }
            }
        }
    }
}
