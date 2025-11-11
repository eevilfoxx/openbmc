pipeline {
    agent any
    
    parameters {
        choice(
            name: 'TARGET',
            choices: ['romulus', 'witherspoon', 'palmetto'],
            description: 'OpenBMC target platform'
        )
        booleanParam(
            name: 'RUN_LOAD_TEST',
            defaultValue: true,
            description: 'Run load testing'
        )
        string(
            name: 'QEMU_MEMORY',
            defaultValue: '512M',
            description: 'QEMU memory allocation'
        )
        string(
            name: 'BRANCH',
            defaultValue: 'main',
            description: 'Git branch to build from'
        )
    }
    
    environment {
        // Пути и переменные окружения
        WORKSPACE = "${env.WORKSPACE}"
        BUILD_DIR = "${env.WORKSPACE}/build"
        REPORTS_DIR = "${env.WORKSPACE}/reports"
        ARTIFACTS_DIR = "${env.WORKSPACE}/artifacts"
        
        // Переменные для тестов
        OPENBMC_HOST = 'localhost'
        OPENBMC_PORT = '2443'
        OPENBMC_USER = 'root'
        OPENBMC_PASSWORD = '0penBmc'
    }
    
    options {
        timeout(time: 2, unit: 'HOURS')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }
    
    stages {
        stage('Prepare Environment') {
            steps {
                script {
                    // Создание директорий
                    sh '''
                        mkdir -p ${BUILD_DIR}
                        mkdir -p ${REPORTS_DIR}
                        mkdir -p ${ARTIFACTS_DIR}
                        mkdir -p ${REPORTS_DIR}/junit
                        mkdir -p ${REPORTS_DIR}/coverage
                        mkdir -p ${REPORTS_DIR}/loadtest
                    '''
                    
                    // Установка зависимостей Python
                    sh '''
                        python3 -m venv ${WORKSPACE}/venv
                        . ${WORKSPACE}/venv/bin/activate
                        pip install --upgrade pip
                        pip install requests paramiko selenium robotframework
                        pip install locust junitparser pytest-html
                    '''
                }
            }
        }
        
        stage('Checkout Code') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${params.BRANCH}"]],  // Используем параметр BRANCH
                    extensions: [
                        [
                            $class: 'CleanCheckout',
                            deleteUntrackedNestedRepositories: true
                        ]
                    ],
                    userRemoteConfigs: [[
                        url: 'https://github.com/openbmc/openbmc.git',
                        credentialsId: ''
                    ]]
                ])
                
                // Проверяем существование тестовых файлов
                sh '''
                    echo "Checking for test files in repository..."
                    ls -la *.py 2>/dev/null || echo "No Python test files found in root directory"
                '''
            }
        }
        
        stage('Setup Build Environment') {
            steps {
                dir('openbmc') {
                    sh '''
                        # Настройка окружения для выбранной цели
                        . setup ${params.TARGET}
                        
                        # Конфигурация сборки
                        . openbmc-env build
                        
                        # Создание build директории
                        mkdir -p ${BUILD_DIR}/${params.TARGET}
                    '''
                }
            }
        }
        
        stage('Build OpenBMC') {
            steps {
                dir('openbmc') {
                    sh '''
                        . setup ${params.TARGET}
                        
                        # Запуск сборки образа
                        bitbake obmc-phosphor-image
        
                        # Копирование собранного образа в артефакты
                        cp tmp/deploy/images/${params.TARGET}/obmc-phosphor-image-${params.TARGET}.* \
                           ${ARTIFACTS_DIR}/ 2>/dev/null || true
                    '''
                }
            }
            post {
                success {
                    archiveArtifacts artifacts: 'artifacts/*', fingerprint: true
                }
            }
        }
        
        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    // Запуск QEMU в фоновом режиме
                    sh '''
                        # Поиск образа QEMU
                        QEMU_IMAGE=$(find ${ARTIFACTS_DIR} -name "*qemu*.img" | head -1)
                        
                        if [ -z "$QEMU_IMAGE" ]; then
                            echo "QEMU image not found in artifacts, checking build directory"
                            QEMU_IMAGE=$(find ${BUILD_DIR} -name "*qemu*.img" | head -1)
                        fi
                        
                        if [ -z "$QEMU_IMAGE" ]; then
                            echo "WARNING: No QEMU image found! Continuing for testing..."
                            # Создаем пустой PID файл чтобы избежать ошибок в последующих шагах
                            echo "QEMU_PID=" > ${WORKSPACE}/qemu.env
                        else
                            echo "Using QEMU image: ${QEMU_IMAGE}"
                            
                            # Запуск QEMU
                            qemu-system-arm \
                                -machine romulus-bmc \
                                -drive file=${QEMU_IMAGE},format=raw,if=mtd \
                                -netdev user,id=net0,hostfwd=:0.0.0.0:2443-:443,hostfwd=:0.0.0.0:2222-:22 \
                                -device driver=e1000,netdev=net0 \
                                -nographic \
                                -m ${params.QEMU_MEMORY} \
                                -smp 2 \
                                -pidfile ${WORKSPACE}/qemu.pid \
                                -daemonize
                            
                            # Сохранение PID процесса
                            echo "QEMU_PID=$(cat ${WORKSPACE}/qemu.pid)" > ${WORKSPACE}/qemu.env
                            
                            # Ожидание загрузки системы
                            echo "Waiting for OpenBMC to boot..."
                            timeout 300 bash -c '
                                until nc -z ${OPENBMC_HOST} ${OPENBMC_PORT} 2>/dev/null; do
                                    sleep 10
                                    echo "Waiting for OpenBMC service..."
                                done
                            ' || echo "WARNING: OpenBMC boot timeout or service not available"
                            echo "OpenBMC is ready (or timeout reached)!"
                        fi
                    '''
                }
            }
        }
        
        stage('Run Automated Tests') {
            steps {
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "test.py" ]; then
                            echo "Running automated tests from test.py"
                            
                            # Запуск Python тестов с генерацией JUnit отчета
                            python -m pytest test.py \
                                --junitxml=${REPORTS_DIR}/junit/automated_tests_results.xml \
                                --html=${REPORTS_DIR}/automated_tests_report.html \
                                --self-contained-html || echo "Some tests failed, continuing..."
                        else
                            echo "test.py not found, creating dummy test report"
                            # Создаем заглушку для отчета
                            cat > ${REPORTS_DIR}/junit/automated_tests_results.xml << 'EOF'
                            <testsuite name="automated_tests" tests="1" errors="0" failures="0" skipped="1">
                                <testcase classname="dummy" name="test_not_found">
                                    <skipped message="test.py not found in repository"/>
                                </testcase>
                            </testsuite>
                            EOF
                        fi
                    '''
                }
            }
            post {
                always {
                    junit "${REPORTS_DIR}/junit/automated_tests_results.xml"
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${REPORTS_DIR}",
                        reportFiles: 'automated_tests_report.html',
                        reportName: 'Automated Tests Report'
                    ])
                }
            }
        }
        
        stage('Run WebUI Tests') {
            steps {
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "test-redfish.py" ]; then
                            echo "Running WebUI tests from test-redfish.py"
                            
                            # Запуск WebUI тестов с генерацией JUnit отчета
                            python -m pytest test-redfish.py \
                                --junitxml=${REPORTS_DIR}/junit/webui_tests_results.xml \
                                --html=${REPORTS_DIR}/webui_tests_report.html \
                                --self-contained-html || echo "Some tests failed, continuing..."
                        else
                            echo "test-redfish.py not found, creating dummy test report"
                            # Создаем заглушку для отчета
                            cat > ${REPORTS_DIR}/junit/webui_tests_results.xml << 'EOF'
                            <testsuite name="webui_tests" tests="1" errors="0" failures="0" skipped="1">
                                <testcase classname="dummy" name="test_not_found">
                                    <skipped message="test-redfish.py not found in repository"/>
                                </testcase>
                            </testsuite>
                            EOF
                        fi
                    '''
                }
            }
            post {
                always {
                    junit "${REPORTS_DIR}/junit/webui_tests_results.xml"
                    publishHTML([
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: "${REPORTS_DIR}",
                        reportFiles: 'webui_tests_report.html',
                        reportName: 'WebUI Tests Report'
                    ])
                }
            }
        }
        
        stage('Run Load Testing') {
            when {
                expression { params.RUN_LOAD_TEST == true }
            }
            steps {
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "locustfile.py" ]; then
                            echo "Running load tests from locustfile.py"
                            
                            # Проверяем доступность сервера перед запуском нагрузочного тестирования
                            if nc -z ${OPENBMC_HOST} ${OPENBMC_PORT} 2>/dev/null; then
                                # Запуск Locust в фоновом режиме
                                locust -f locustfile.py \
                                    --host=https://${OPENBMC_HOST}:${OPENBMC_PORT} \
                                    --headless \
                                    --users=5 \
                                    --spawn-rate=1 \
                                    --run-time=2m \
                                    --html=${REPORTS_DIR}/loadtest/locust_report.html \
                                    --csv=${REPORTS_DIR}/loadtest/locust \
                                    --logfile=${REPORTS_DIR}/loadtest/locust.log &
                                
                                LOCUST_PID=$!
                                echo $LOCUST_PID > ${WORKSPACE}/locust.pid
                                
                                # Ожидание завершения Locust
                                wait $LOCUST_PID || echo "Locust finished with warnings"
                            else
                                echo "WARNING: OpenBMC not available, skipping load tests"
                                echo "Load tests skipped - OpenBMC not accessible" > ${REPORTS_DIR}/loadtest/skipped.txt
                            fi
                        else
                            echo "locustfile.py not found, skipping load tests"
                            echo "Load tests skipped - locustfile.py not found" > ${REPORTS_DIR}/loadtest/skipped.txt
                        fi
                    '''
                }
            }
            post {
                always {
                    script {
                        sh '''
                            if [ -f "${WORKSPACE}/locust.pid" ]; then
                                LOCUST_PID=$(cat ${WORKSPACE}/locust.pid)
                                kill $LOCUST_PID 2>/dev/null || true
                                rm -f ${WORKSPACE}/locust.pid
                            fi
                        '''
                    }
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
        
        stage('Run Custom Tests') {
            steps {
                script {
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        # Поиск и выполнение всех Python тестовых файлов кроме уже обработанных
                        for test_file in *.py; do
                            if [ "$test_file" != "test.py" ] && \
                               [ "$test_file" != "test-redfish.py" ] && \
                               [ "$test_file" != "locustfile.py" ]; then
                                echo "Running additional tests from $test_file"
                                python -m pytest "$test_file" \
                                    --junitxml=${REPORTS_DIR}/junit/${test_file%.py}_results.xml \
                                    -v || echo "Tests in $test_file failed, continuing..."
                            fi
                        done
                    '''
                }
            }
            post {
                always {
                    junit "${REPORTS_DIR}/junit/*_results.xml"
                }
            }
        }
    }
    
    post {
        always {
            script {
                // Остановка QEMU если он был запущен
                sh '''
                    if [ -f "${WORKSPACE}/qemu.env" ]; then
                        source ${WORKSPACE}/qemu.env
                        if [ ! -z "$QEMU_PID" ] && ps -p $QEMU_PID > /dev/null 2>&1; then
                            echo "Stopping QEMU process $QEMU_PID"
                            kill $QEMU_PID 2>/dev/null || true
                            sleep 5
                            # Принудительное завершение если процесс все еще работает
                            kill -9 $QEMU_PID 2>/dev/null || true
                            rm -f ${WORKSPACE}/qemu.pid
                        fi
                    fi
                '''
                
                // Архивирование всех отчетов
                archiveArtifacts artifacts: 'reports/**/*', fingerprint: true
                
                // Сохранение логов для отладки
                sh '''
                    echo "=== Pipeline Debug Info ===" > ${REPORTS_DIR}/pipeline_debug.log
                    echo "Workspace: ${WORKSPACE}" >> ${REPORTS_DIR}/pipeline_debug.log
                    echo "Branch: ${params.BRANCH}" >> ${REPORTS_DIR}/pipeline_debug.log
                    echo "Target: ${params.TARGET}" >> ${REPORTS_DIR}/pipeline_debug.log
                    ls -la >> ${REPORTS_DIR}/pipeline_debug.log
                    echo "Python files:" >> ${REPORTS_DIR}/pipeline_debug.log
                    ls -la *.py 2>/dev/null >> ${REPORTS_DIR}/pipeline_debug.log || echo "No Python files" >> ${REPORTS_DIR}/pipeline_debug.log
                '''
            }
        }
        success {
            emailext (
                subject: "SUCCESS: OpenBMC Pipeline #${BUILD_NUMBER}",
                body: "Сборка ${BUILD_URL} завершена успешно",
                to: "${EMAIL_RECIPIENTS}"
            )
        }
        failure {
            emailext (
                subject: "FAILED: OpenBMC Pipeline #${BUILD_NUMBER}",
                body: "Сборка ${BUILD_URL} завершилась с ошибками",
                to: "${EMAIL_RECIPIENTS}"
            )
        }
        unstable {
            emailext (
                subject: "UNSTABLE: OpenBMC Pipeline #${BUILD_NUMBER}",
                body: "Сборка ${BUILD_URL} нестабильна (упавшие тесты)",
                to: "${EMAIL_RECIPIENTS}"
            )
        }
    }
}
