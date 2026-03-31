# CUEMS shell aliases
alias cuems-restart='sudo systemctl restart cuems-node.target cuems-controller.target'
alias cuems-start='sudo systemctl start cuems-node.target cuems-controller.target'
alias cuems-stop='sudo systemctl stop cuems-controller.target cuems-node.target'
alias cuems-status='systemctl status cuems-node.target cuems-controller.target'
