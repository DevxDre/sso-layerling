<?php

namespace Sso\Layerling\Oidc\Http;

use RuntimeException;

/** Anbieter nicht erreichbar, Zeitüberschreitung, TLS- oder Größenfehler */
final class TransportException extends RuntimeException
{
}
