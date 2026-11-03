<?php

use Tests\TestCase;

// Los tests de integración arrancan la aplicación; los unitarios son PHP puro (constitución §3).
pest()->extend(TestCase::class)->in('Integration');
