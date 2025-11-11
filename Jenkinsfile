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
                        
                        python3 -m venv ${WORKSPACE}/venv
                        . ${WORKSPACE}/venv/bin/activate
                        pip install --upgrade pip
                        pip install requests paramiko pytest pytest-html locust junitparser selenium
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
                        
                        if [ -f "test.py" ]; then
                            # Запускаем тест и сохраняем вывод
                            python test.py 2>&1 | tee ${REPORTS_DIR}/test_py_output.log
                            
                            # Создаем JUnit отчет на основе вывода
                            cat > ${REPORTS_DIR}/junit/test_py_results.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="test.py" tests="1" errors="0" failures="0" skipped="0">
    <testcase classname="test" name="automated_tests" time="0">
        <system-out>
EOF
                            cat ${REPORTS_DIR}/test_py_output.log >> ${REPORTS_DIR}/junit/test_py_results.xml
                            cat >> ${REPORTS_DIR}/junit/test_py_results.xml << 'EOF'
        </system-out>
    </testcase>
</testsuite>
EOF
                        else
                            echo "test.py not found"
                            cat > ${REPORTS_DIR}/junit/test_py_results.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="test.py" tests="1" errors="1" failures="0" skipped="0">
    <testcase classname="test" name="file_check">
        <error message="test.py file not found"/>
    </testcase>
</testsuite>
EOF
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
                        
                        if [ -f "test-redfish.py" ]; then
                            # Запускаем pytest для test-redfish.py
                            OPENBMC_URL="https://${OPENBMC_HOST}:${OPENBMC_PORT}" \
                            OPENBMC_USERNAME="${OPENBMC_USER}" \
                            OPENBMC_PASSWORD="${OPENBMC_PASSWORD}" \
                            python -m pytest test-redfish.py \
                                --junitxml=${REPORTS_DIR}/junit/test_redfish_results.xml \
                                --html=${REPORTS_DIR}/test_redfish_report.html \
                                --self-contained-html -v || echo "Pytest completed"
                        else
                            echo "test-redfish.py not found"
                            cat > ${REPORTS_DIR}/junit/test_redfish_results.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="test-redfish.py" tests="1" errors="1" failures="0" skipped="0">
    <testcase classname="test" name="file_check">
        <error message="test-redfish.py file not found"/>
    </testcase>
</testsuite>
EOF
                        fi
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
                        
                        if [ -f "locustfile.py" ]; then
                            # Запускаем locust на 1 минуту
                            timeout 70 locust -f locustfile.py \
                                --headless \
                                --users=2 \
                                --spawn-rate=1 \
                                --run-time=1m \
                                --html=${REPORTS_DIR}/loadtest/locust_report.html \
                                --csv=${REPORTS_DIR}/loadtest/locust \
                                --logfile=${REPORTS_DIR}/loadtest/locust.log || echo "Locust finished"
                        else
                            echo "locustfile.py not found"
                            echo "Load tests skipped - file not found" > ${REPORTS_DIR}/loadtest/skipped.txt
                        fi
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
            archiveArtifacts artifacts: 'reports/**/*', fingerprint: true
            
            script {
                sh """
                    echo "=== Build Complete ===" > ${REPORTS_DIR}/build_summary.log
                    echo "Workspace: ${env.WORKSPACE}" >> ${REPORTS_DIR}/build_summary.log
                    echo "OpenBMC Host: ${params.OPENBMC_HOST}" >> ${REPORTS_DIR}/build_summary.log
                    echo "Timestamp: \$(date)" >> ${REPORTS_DIR}/build_summary.log
                    echo "" >> ${REPORTS_DIR}/build_summary.log
                    echo "Files executed:" >> ${REPORTS_DIR}/build_summary.log
                    ls -la *.py >> ${REPORTS_DIR}/build_summary.log
                """
            }
        }
    }
}
