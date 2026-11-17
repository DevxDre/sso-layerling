<?php
declare(strict_types=1);

$gateway = require dirname(__DIR__) . '/private/src/bootstrap.php';
$gateway->session();
