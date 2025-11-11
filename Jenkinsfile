pipeline {
    agent any
    
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
        stage('Prepare Environment') {
            steps {
                script {
                    sh '''
                        mkdir -p ${REPORTS_DIR}
                        mkdir -p ${REPORTS_DIR}/junit
                        mkdir -p ${REPORTS_DIR}/loadtest
                        
                        # Устанавливаем системные зависимости для Chrome
                        apt-get update
                        apt-get install -y wget unzip
                        
                        # Устанавливаем Chrome
                        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
                        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
                        apt-get update
                        apt-get install -y google-chrome-stable
                        
                        # Устанавливаем ChromeDriver
                        CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
                        wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}.0.0/linux64/chromedriver-linux64.zip"
                        unzip chromedriver-linux64.zip
                        mv chromedriver-linux64/chromedriver /usr/local/bin/
                        chmod +x /usr/local/bin/chromedriver
                        
                        # Устанавливаем Python зависимости
                        python3 -m venv ${WORKSPACE}/venv
                        . ${WORKSPACE}/venv/bin/activate
                        pip install --upgrade pip
                        pip install requests paramako pytest pytest-html locust junitparser selenium webdriver-manager
                    '''
                }
            }
        }
        
        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        echo "Starting QEMU with OpenBMC..."
                        
                        # Запускаем QEMU в фоне с правильными параметрами
                        qemu-system-arm -m 256 -M romulus-bmc -nographic \
                          -drive file=romulus/obmc-phosphor-image-romulus-20250920111732.static.mtd,format=raw,if=mtd \
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
                        . ${WORKSPACE}/venv/bin/activate
                        echo "Running test.py..."
                        
                        # Устанавливаем правильный путь к ChromeDriver для Selenium
                        export PATH=$PATH:/usr/local/bin
                        
                        # Запускаем test.py и сохраняем вывод
                        python test.py 2>&1 | tee ${REPORTS_DIR}/test_py_output.log
                        TEST_EXIT_CODE=${PIPESTATUS[0]}
                        
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
                        . ${WORKSPACE}/venv/bin/activate
                        echo "Running test-redfish.py..."
                        
                        # Запускаем pytest для test-redfish.py
                        OPENBMC_URL="https://${OPENBMC_HOST}:${OPENBMC_PORT}" \
                        OPENBMC_USERNAME="${OPENBMC_USER}" \
                        OPENBMC_PASSWORD="${OPENBMC_PASSWORD}" \
                        python -m pytest test-redfish.py \
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
                        . ${WORKSPACE}/venv/bin/activate
                        echo "Running load tests from locustfile.py..."
                        
                        # Запускаем locust на 1 минуту
                        timeout 70 locust -f locustfile.py \
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
                    fi
                '''
            }
            
            archiveArtifacts artifacts: 'reports/**/*', fingerprint: true
        }
    }
}
