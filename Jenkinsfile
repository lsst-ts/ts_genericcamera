pipeline {
    agent any
    environment {
        container_name = "c_${BUILD_ID}_${JENKINS_NODE_COOKIE}"
        user_ci = credentials('lsst-io')
        XML_REPORT="jenkinsReport/report.xml"
        work_branches = "${GIT_BRANCH} ${CHANGE_BRANCH} develop"
    }
    stages {
        stage("Pulling image.") {
            steps {
                script {
                    sh """
                    docker pull lsstts/develop-env:develop
                    """
                }
            }
        }
        stage("Start container") {
            steps {
                script {
                    sh """
                    container=\$(docker run -v \${WORKSPACE}:/home/saluser/repo/ -td --rm --name \${container_name} -e LTD_USERNAME=\${user_ci_USR} -e LTD_PASSWORD=\${user_ci_PSW} lsstts/salobj:develop)
                    """
                }
            }
        }
        stage("Checkout sal") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_sal && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout salobj") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_salobj && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout xml") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_xml && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Checkout IDL") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_idl && /home/saluser/.checkout_repo.sh \${work_branches} && git pull\"
                    """
                }
            }
        }
        stage("Build IDL files") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && setup ts_sal -t current && make_idl_files.py GenericCamera GCHeaderService\"
                    """
                }
            }
        }
        stage("Checkout config_ocs") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd /home/saluser/repos/ts_config_ocs/ && /home/saluser/.checkout_repo.sh \${work_branches} \"
                    """
                }
            }
        }
        stage("Running tests") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd repo && pip install --ignore-installed -e . && eups declare -r . -t saluser && setup ts_genericcamera -t saluser && pytest --junitxml=\${XML_REPORT}\"
                    """
                }
            }
        }
        stage("Build and Upload Documentation") {
            steps {
                script {
                    sh """
                    docker exec -u saluser \${container_name} sh -c \"source ~/.setup.sh && cd repo && pip install --ignore-installed -e . && pip install -r doc/requirements.txt && package-docs build && pip install ltd-conveyor && ltd upload --product ts-genericcamera --git-ref ${GIT_BRANCH} --dir doc/_build/html\"
                    """
                }
            }
        }
    }
    post {
        always {
            // Publish the HTML report
            publishHTML (target: [
                allowMissing: false,
                alwaysLinkToLastBuild: false,
                keepAll: true,
                reportDir: 'jenkinsReport/',
                reportFiles: 'index.html',
                reportName: "Coverage Report"
              ])
         }
        cleanup {
            sh """
                docker stop \${container_name} || echo Could not stop container
            """
            deleteDir()
        }
    }
}
