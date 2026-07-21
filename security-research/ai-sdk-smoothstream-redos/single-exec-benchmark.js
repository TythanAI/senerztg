// (a) single exec cost of /\S+\s+/m on N non-whitespace chars
const re = /\S+\s+/m;
console.log('== single .exec() on N non-whitespace chars ==');
for (const N of [5000, 20000, 50000, 100000, 200000]) {
  const s = 'a'.repeat(N);
  const t = process.hrtime.bigint();
  re.exec(s);
  const ms = Number(process.hrtime.bigint()-t)/1e6;
  console.log(`  N=${N}: ${ms.toFixed(1)}ms`);
}
