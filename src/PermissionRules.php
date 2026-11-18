<?php
declare(strict_types=1);

namespace Sso\Layerling;

/** The caller holds authorization.lock while reading or changing these rules. */
final class PermissionRules
{
    public const OPERATIONS = [
        'read' => 'Konten auflisten und Inhalte einsehen',
        'write' => 'Inhalte bearbeiten',
        'delete' => 'Inhalte löschen',
        'publish' => 'Vorlagen verteilen',
        'mcp' => 'MCP-Token erstellen',
    ];
    private const LIMIT = 131072;
    private array $rules = [];
    private array $patterns = [];

    public function __construct(private readonly string $path)
    {
        if (is_link($path)) {
            throw new \RuntimeException('Invalid permission file');
        }
        if (!file_exists($path)) {
            return;
        }
        $raw = is_file($path) ? file_get_contents($path, false, null, 0, self::LIMIT + 1) : false;
        $data = is_string($raw) && strlen($raw) <= self::LIMIT
            ? json_decode($raw, true, 16, JSON_THROW_ON_ERROR) : null;
        if (($data['version'] ?? null) !== 1
            || !is_array($data['rules'] ?? null) || !array_is_list($data['rules'])
            || !is_array($data['patterns'] ?? null) || !array_is_list($data['patterns'])) {
            throw new \RuntimeException('Invalid permission file');
        }
        foreach ($data['rules'] as $rule) {
            if (!is_array($rule) || self::normalize($rule) !== $rule || isset($this->rules[self::key($rule)])) {
                throw new \RuntimeException('Invalid permission rule');
            }
            $this->rules[self::key($rule)] = $rule;
        }
        foreach ($data['patterns'] as $pattern) {
            if (!self::validPattern($pattern)) {
                throw new \RuntimeException('Invalid group pattern');
            }
        }
        $this->patterns = $data['patterns'];
    }

    private static function selector(mixed $value): bool
    {
        return is_string($value) && preg_match('/^(?:group:[A-Za-z0-9_-]{1,128}|role:[A-Za-z0-9_.:-]{1,100})$/D', $value) === 1;
    }

    private static function normalize(array $input): ?array
    {
        $actor = $input['actor'] ?? null;
        $owner = $input['owner'] ?? '';
        $operation = $input['operation'] ?? null;
        $effect = $input['effect'] ?? null;
        if (!self::selector($actor) || !is_string($operation) || !isset(self::OPERATIONS[$operation])
            || !in_array($effect, ['allow', 'deny'], true)) {
            return null;
        }
        $needsOwner = in_array($operation, ['read', 'write', 'delete'], true);
        if ($needsOwner ? !self::selector($owner) : $owner !== '') {
            return null;
        }
        return compact('actor', 'owner', 'operation', 'effect');
    }

    private static function validPattern(mixed $value): bool
    {
        return is_string($value) && preg_match('/^[A-Za-z0-9_.:-]{1,128}\^?$/D', $value) === 1;
    }

    private static function key(array $rule): string
    {
        return hash('sha256', json_encode([$rule['actor'], $rule['owner'], $rule['operation']], JSON_THROW_ON_ERROR));
    }

    public function rules(): array { return $this->rules; }
    public function patterns(): array { return $this->patterns; }

    public function change(array $form): bool
    {
        $action = $form['action'] ?? null;
        if ($action === 'save-rule') {
            $rule = self::normalize($form);
            if ($rule === null) {
                return false;
            }
            $this->rules[self::key($rule)] = $rule;
        } elseif ($action === 'remove-rule') {
            $key = $form['key'] ?? null;
            if (!is_string($key) || !isset($this->rules[$key]) || $this->rules[$key]['effect'] !== ($form['effect'] ?? null)) {
                return false;
            }
            unset($this->rules[$key]);
        } elseif (in_array($action, ['add-pattern', 'remove-pattern'], true)) {
            $pattern = $form['pattern'] ?? null;
            if (!self::validPattern($pattern)) {
                return false;
            }
            $this->patterns = array_values(array_diff($this->patterns, [$pattern]));
            if ($action === 'add-pattern') {
                $this->patterns[] = $pattern;
            }
        } else {
            return false;
        }

        $json = json_encode(['version' => 1, 'rules' => array_values($this->rules),
            'patterns' => $this->patterns], JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT);
        if (strlen($json) > self::LIMIT) {
            return false;
        }
        $tmp = tempnam(dirname($this->path), '.permissions-');
        try {
            if ($tmp === false || file_put_contents($tmp, $json) !== strlen($json) || !rename($tmp, $this->path)) {
                throw new \RuntimeException('Could not save permissions');
            }
        } finally {
            if ($tmp !== false && is_file($tmp)) {
                unlink($tmp);
            }
        }
        return true;
    }

    private static function matches(array $record, string $selector): bool
    {
        [$kind, $id] = explode(':', $selector, 2);
        return in_array($id, $record[$kind === 'role' ? 'roles' : 'groups'], true);
    }

    public function decision(string $operation, array $actor, ?array $owner = null): ?bool
    {
        $allowed = null;
        foreach ($this->rules as $rule) {
            if ($rule['operation'] !== $operation || !self::matches($actor, $rule['actor'])
                || ($owner !== null && !self::matches($owner, $rule['owner']))) {
                continue;
            }
            if ($rule['effect'] === 'deny') {
                return false;
            }
            $allowed = true;
        }
        return $allowed;
    }

    public function templateGroups(array $record): array
    {
        if ($this->patterns === []) {
            return $record['groups'];
        }
        return array_values(array_filter($record['groups'], function (string $id) use ($record): bool {
            $account = $record['groupAccounts'][$id] ?? null;
            $account = is_string($account) ? $account : $id;
            foreach ($this->patterns as $pattern) {
                if (str_ends_with($pattern, '^') ? str_starts_with($account, substr($pattern, 0, -1)) : $account === $pattern) {
                    return true;
                }
            }
            return false;
        }));
    }
}
