pipeline {
    agent {
        docker {
            image 'your-username/jenkins-selenium-openbmc:latest'  // Используйте ваш собранный образ
            args '-u root --privileged --network host -v /dev/shm:/dev/shm'  // Привилегии для Chrome и shared memory
            reuseNode true
        }
    }
    
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
        VENV_PATH = '/opt/selenium-venv'
        PYTHON_PATH = "/opt/selenium-venv/bin/python3"
        PIP_PATH = "/opt/selenium-venv/bin/pip"
    }
    
    stages {
        stage('Prepare Environment') {
            steps {
                script {
                    sh '''
                        mkdir -p ${REPORTS_DIR}
                        mkdir -p ${REPORTS_DIR}/junit
                        mkdir -p ${REPORTS_DIR}/loadtest
                        
                        # Проверяем установленные зависимости
                        echo "=== Checking dependencies ==="
                        which python3 && python3 --version
                        which ${PYTHON_PATH} && ${PYTHON_PATH} --version
                        google-chrome --version
                        which chromedriver && chromedriver --version
                        
                        # Проверяем установленные Python пакеты
                        ${PIP_PATH} list | grep -E "selenium|webdriver-manager|requests|paramiko|pytest|locust"
                    '''
                }
            }
        }
        
        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    sh '''
                        # Используем Python из виртуального окружения
                        ${PYTHON_PATH} --version
                        
                        echo "Starting QEMU with OpenBMC..."
                        
                        # Запускаем QEMU в фоне с правильными параметрами
                        # Предполагаем, что образ QEMU доступен в workspace
                        qemu-system-arm -m 256 -M romulus-bmc -nographic \
                          -drive file=${WORKSPACE}/romulus/obmc-phosphor-image-romulus.static.mtd,format=raw,if=mtd \
                          -net nic \
                          -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::623-:623,hostname=qemu \
                          -pidfile ${WORKSPACE}/qemu.pid \
                          -daemonize
                        
                        echo "QEMU_PID=$(cat ${WORKSPACE}/qemu.pid)" > ${WORKSPACE}/qemu.env
                        
                        # Ждем загрузки OpenBMC
                        echo "Waiting for OpenBMC to boot..."
                        timeout 120 bash -c '
                            until nc -z ${OPENBMC_HOST} ${OPENBMC_PORT}; do
                                sleep 10
                                echo "Waiting for OpenBMC service..."
                            done
                        '
                        echo "OpenBMC is ready!"
                    '''
                }
            }
        }
        
        stage('Run Automated Tests (test.py)') {
            steps {
                script {
                    sh '''
                        echo "Running test.py with ${PYTHON_PATH}..."
                        
                        # Устанавливаем переменные окружения для Selenium
                        export DISPLAY=:99
                        export PATH=$PATH:/usr/local/bin
                        
                        # Запускаем Xvfb для headless тестирования (если нужно)
                        Xvfb :99 -screen 0 1920x1080x24 &
                        XVFB_PID=$!
                        
                        # Запускаем test.py и сохраняем вывод
                        ${PYTHON_PATH} ${WORKSPACE}/test.py 2>&1 | tee ${REPORTS_DIR}/test_py_output.log
                        TEST_EXIT_CODE=${PIPESTATUS[0]}
                        
                        # Останавливаем Xvfb
                        kill $XVFB_PID 2>/dev/null || true
                        
                        # Создаем JUnit отчет
                        cat > ${REPORTS_DIR}/junit/test_py_results.xml << EOF
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="test.py" tests="1" errors="0" failures="0" skipped="0">
    <testcase classname="test" name="automated_tests" time="0">
        <system-out>
EOF
                        cat ${REPORTS_DIR}/test_py_output.log >> ${REPORTS_DIR}/junit/test_py_results.xml
                        cat >> ${REPORTS_DIR}/junit/test_py_results.xml << EOF
        </system-out>
    </testcase>
</testsuite>
EOF
                        
                        # Если тест упал, выходим с ошибкой
                        if [ $TEST_EXIT_CODE -ne 0 ]; then
                            echo "test.py failed with exit code $TEST_EXIT_CODE"
                            exit $TEST_EXIT_CODE
                        fi
                    '''
                }
            }
            post {
                always {
                    junit "${REPORTS_DIR}/junit/test_py_results.xml"
                }
            }
        }
        
        stage('Run Redfish Tests (test-redfish.py)') {
            steps {
                script {
                    sh '''
                        echo "Running test-redfish.py with ${PYTHON_PATH}..."
                        
                        # Запускаем pytest для test-redfish.py через виртуальное окружение
                        OPENBMC_URL="https://${OPENBMC_HOST}:${OPENBMC_PORT}" \
                        OPENBMC_USERNAME="${OPENBMC_USER}" \
                        OPENBMC_PASSWORD="${OPENBMC_PASSWORD}" \
                        ${PYTHON_PATH} -m pytest ${WORKSPACE}/test-redfish.py \
                            --junitxml=${REPORTS_DIR}/junit/test_redfish_results.xml \
                            --html=${REPORTS_DIR}/test_redfish_report.html \
                            --self-contained-html -v
                    '''
                }
            }
            post {
                always {
                    junit "${REPORTS_DIR}/junit/test_redfish_results.xml"
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${REPORTS_DIR}",
                        reportFiles: 'test_redfish_report.html',
                        reportName: 'Redfish Tests Report'
                    ])
                }
            }
        }
        
        stage('Run Load Tests (locustfile.py)') {
            when {
                expression { params.RUN_LOAD_TEST == true }
            }
            steps {
                script {
                    sh '''
                        echo "Running load tests from locustfile.py..."
                        
                        # Запускаем locust через виртуальное окружение
                        timeout 70 ${VENV_PATH}/bin/locust -f ${WORKSPACE}/locustfile.py \
                            --headless \
                            --users=2 \
                            --spawn-rate=1 \
                            --run-time=1m \
                            --html=${REPORTS_DIR}/loadtest/locust_report.html \
                            --csv=${REPORTS_DIR}/loadtest/locust \
                            --logfile=${REPORTS_DIR}/loadtest/locust.log
                    '''
                }
            }
            post {
                always {
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${REPORTS_DIR}/loadtest",
                        reportFiles: 'locust_report.html',
                        reportName: 'Load Test Report'
                    ])
                    archiveArtifacts artifacts: 'reports/loadtest/locust*.csv', fingerprint: true
                }
            }
        }
        
        stage('Run Selenium Tests') {
            steps {
                script {
                    sh '''
                        echo "Running Selenium tests..."
                        
                        # Пример запуска Selenium теста
                        ${PYTHON_PATH} -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

# Используем системный chromedriver или webdriver-manager
try:
    # Пытаемся использовать системный chromedriver
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
except:
    # Fallback на webdriver-manager
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

try:
    driver.get('https://${OPENBMC_HOST}:${OPENBMC_PORT}')
    print('Page title:', driver.title)
    print('Selenium test passed successfully!')
finally:
    driver.quit()
"
                    '''
                }
            }
        }
    }
    
    post {
        always {
            script {
                // Останавливаем QEMU
                sh '''
                    if [ -f "${WORKSPACE}/qemu.env" ]; then
                        source ${WORKSPACE}/qemu.env
                        if [ ! -z "$QEMU_PID" ]; then
                            kill $QEMU_PID 2>/dev/null || true
                            rm -f ${WORKSPACE}/qemu.pid
                        fi
                        rm -f ${WORKSPACE}/qemu.env
                    fi
                '''
            }
            
            archiveArtifacts artifacts: 'reports/**/*', fingerprint: true
            
            // Очистка
            sh '''
                rm -rf ${WORKSPACE}/__pycache__ || true
                rm -rf ${WORKSPACE}/.pytest_cache || true
            '''
        }
    }
}
