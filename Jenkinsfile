pipeline {
    agent any

    environment {
        MAVEN_HOME = tool name: 'maven-3.9', type: 'maven'
    }

    stages {
        stage('后端构建 + 单元测试') {
            steps {
                dir('backend') {
                    sh 'mvn clean verify'
                }
            }
        }
        stage('前端构建') {
            steps {
                dir('frontend') {
                    sh 'npm install && npm run build'
                }
            }
        }
        stage('产物归档') {
            steps {
                archiveArtifacts artifacts: 'backend/target/*.jar', fingerprint: true
            }
        }
    }
}
