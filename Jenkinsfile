pipeline {
    agent {
        docker {
            image 'python:3.9-slim'
            args '-v /dev:/dev --privileged'
        }
    }
    
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
        WORKSPACE = "${env.WORKSPACE}"
        BUILD_DIR = "${env.WORKSPACE}/build"
        REPORTS_DIR = "${env.WORKSPACE}/reports"
        ARTIFACTS_DIR = "${env.WORKSPACE}/artifacts"
        
        OPENBMC_HOST = 'localhost'
        OPENBMC_PORT = '2443'
        OPENBMC_USER = 'root'
        OPENBMC_PASSWORD = '0penBmc'
        
        EMAIL_RECIPIENTS = 'admin@example.com'
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
                    
                    // Установка системных зависимостей в контейнере
                    sh '''
                        apt-get update && apt-get install -y \
                            git build-essential \
                            qemu-system-arm \
                            netcat-openbsd \
                            curl wget \
                            && rm -rf /var/lib/apt/lists/*
                    '''
                    
                    // Установка Python зависимостей
                    sh '''
                        pip install --upgrade pip
                        pip install requests paramiko selenium robotframework
                        pip install locust junitparser pytest-html pytest
                    '''
                }
            }
        }
        
        // Остальные stages остаются без изменений...
        stage('Checkout Code') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${params.BRANCH}"]],
                    extensions: [[$class: 'CleanBeforeCheckout']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/openbmc/openbmc.git',
                        credentialsId: ''
                    ]]
                ])
            }
        }
        
        // ... остальные stages
    }
    
    // Post actions остаются без изменений
}
