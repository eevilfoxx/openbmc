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
                        pip install locust junitparser
                    '''
                }
            }
        }
        
        stage('Checkout Code') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
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
                           ${ARTIFACTS_DIR}/
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
                            echo "QEMU image not found, searching in build directory"
                            QEMU_IMAGE=$(find ${BUILD_DIR} -name "*qemu*.img" | head -1)
                        fi
                        
                        if [ -z "$QEMU_IMAGE" ]; then
                            error "No QEMU image found!"
                        fi
                        
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
                    '''
                    
                    // Ожидание загрузки системы
                    sh '''
                        echo "Waiting for OpenBMC to boot..."
                        timeout 300 bash -c '
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
        
        stage('Run Automated Tests') {
            steps {
                script {
                    // Проверка существования тестового файла
                    sh 'test -f test.py || echo "WARNING: test.py not found, skipping automated tests"'
                    
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "test.py" ]; then
                            echo "Running automated tests from test.py"
                            
                            # Запуск Python тестов с генерацией JUnit отчета
                            python -m pytest test.py \
                                --junitxml=${REPORTS_DIR}/junit/automated_tests_results.xml \
                                --html=${REPORTS_DIR}/automated_tests_report.html \
                                --self-contained-html
                        else
                            echo "test.py not found, skipping automated tests"
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
                    // Проверка существования тестового файла
                    sh 'test -f test-redfish.py || echo "WARNING: test-redfish.py not found, skipping WebUI tests"'
                    
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "test-redfish.py" ]; then
                            echo "Running WebUI tests from test-redfish.py"
                            
                            # Запуск WebUI тестов с генерацией JUnit отчета
                            python -m pytest test-redfish.py \
                                --junitxml=${REPORTS_DIR}/junit/webui_tests_results.xml \
                                --html=${REPORTS_DIR}/webui_tests_report.html \
                                --self-contained-html
                        else
                            echo "test-redfish.py not found, skipping WebUI tests"
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
                    // Проверка существования файла нагрузочного тестирования
                    sh 'test -f locustfile.py || echo "WARNING: locustfile.py not found, skipping load tests"'
                    
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        if [ -f "locustfile.py" ]; then
                            echo "Running load tests from locustfile.py"
                            
                            # Запуск Locust в фоновом режиме
                            locust -f locustfile.py \
                                --host=https://${OPENBMC_HOST}:${OPENBMC_PORT} \
                                --headless \
                                --users=10 \
                                --spawn-rate=1 \
                                --run-time=5m \
                                --html=${REPORTS_DIR}/loadtest/locust_report.html \
                                --csv=${REPORTS_DIR}/loadtest/locust \
                                --logfile=${REPORTS_DIR}/loadtest/locust.log &
                            
                            LOCUST_PID=$!
                            echo $LOCUST_PID > ${WORKSPACE}/locust.pid
                            
                            # Ожидание завершения Locust
                            wait $LOCUST_PID
                            
                        else
                            echo "locustfile.py not found, skipping load tests"
                        fi
                    '''
                }
            }
            post {
                always {
                    script {
                        // Остановка Locust если он все еще работает
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
                    // Универсальный этап для запуска любых других тестов
                    sh '''
                        . ${WORKSPACE}/venv/bin/activate
                        
                        # Поиск и выполнение всех Python тестовых файлов
                        for test_file in *.py; do
                            if [ "$test_file" != "test.py" ] && \
                               [ "$test_file" != "test-redfish.py" ] && \
                               [ "$test_file" != "locustfile.py" ]; then
                                echo "Running additional tests from $test_file"
                                python -m pytest "$test_file" \
                                    --junitxml=${REPORTS_DIR}/junit/${test_file}_results.xml \
                                    -v
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
                // Остановка QEMU
                sh '''
                    if [ -f "${WORKSPACE}/qemu.env" ]; then
                        source ${WORKSPACE}/qemu.env
                        if [ ! -z "$QEMU_PID" ]; then
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
                
                // Сохранение логов
                sh '''
                    if [ -f "${WORKSPACE}/qemu.pid" ]; then
                        echo "QEMU was not properly stopped" > ${REPORTS_DIR}/qemu_cleanup_warning.log
                    fi
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
