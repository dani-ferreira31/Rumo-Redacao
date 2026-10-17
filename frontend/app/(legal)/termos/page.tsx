import type { Metadata } from "next";

export const metadata: Metadata = { title: "Termos de Uso" };

export default function TermsPage() {
  return (
    <>
      <h1>Termos de Uso</h1>
      <p>Última atualização: [DATA].</p>
      <p>
        Estes Termos regem o uso da plataforma Rumo1000 (&quot;Plataforma&quot;), oferecida por [RAZÃO
        SOCIAL], inscrita no CNPJ [CNPJ], com sede em [ENDEREÇO] (&quot;nós&quot;). Ao criar uma conta,
        você concorda com estes Termos e com a <a href="/privacidade">Política de Privacidade</a>.
      </p>

      <h2>1. O que a Plataforma oferece</h2>
      <ul>
        <li>Correção de redações no modelo do ENEM feita por inteligência artificial, com notas por competência e comentários;</li>
        <li>Banco de questões de provas anteriores do ENEM, com estatísticas de desempenho;</li>
        <li>Cronograma de estudos com lembretes por e-mail;</li>
        <li>Provas montadas por professores, respondidas pelo link que o professor compartilha.</li>
      </ul>

      <h2>2. Natureza da correção por IA</h2>
      <p>
        A correção é uma <strong>estimativa automatizada</strong>, gerada por um modelo de
        inteligência artificial a partir dos critérios públicos do INEP. Ela não é a correção
        oficial do ENEM, não garante a nota que você obterá no exame e pode conter erros. Use-a como
        ferramenta de estudo, não como avaliação definitiva.
      </p>
      <p>
        O texto e as fotos das redações são enviados a um provedor de inteligência artificial
        (Google, Anthropic ou OpenAI) para transcrição e correção, como descrito na Política de
        Privacidade.
      </p>

      <h2>3. Conta e idade</h2>
      <ul>
        <li>
          A conta pode ser criada por convite (de aluno ou de professor, sem custo) ou pelo cadastro
          aberto, que exige assinatura.
        </li>
        <li>Você deve informar dados verdadeiros e manter sua senha em sigilo.</li>
        <li>Podemos desativar contas que violem estes Termos.</li>
        <li>
          Menores de 18 anos só podem usar a Plataforma com o consentimento do pai, da mãe ou do
          responsável legal, declarado no cadastro.
        </li>
        <li>Você pode excluir sua conta a qualquer momento pela página de Perfil.</li>
      </ul>

      <h2>4. Assinatura e doações</h2>
      <ul>
        <li>
          Quem se cadastra sem convite paga uma assinatura pelo período informado na página de
          assinatura (por exemplo, R$ 10,00 por 30 dias). O pagamento é feito pelo Mercado Pago,
          com PIX ou cartão, e <strong>não renova sozinho</strong>: avisamos por e-mail perto do
          vencimento.
        </li>
        <li>
          Sem assinatura em dia, a conta continua existindo, mas a correção de redações, o banco
          de questões e o cronograma ficam bloqueados até um novo pagamento. Seus dados não são
          apagados.
        </li>
        <li>
          Você pode desistir da compra em até 7 (sete) dias após o pagamento e receber o valor de
          volta (art. 49 do Código de Defesa do Consumidor), pelo e-mail [E-MAIL DE CONTATO].
        </li>
        <li>
          Doações são voluntárias, de valor escolhido por você, e não dão acesso extra nem
          vantagens na Plataforma.
        </li>
      </ul>

      <h2>5. Uso adequado</h2>
      <p>
        É proibido usar a Plataforma para fins ilícitos, tentar acessar dados de outros usuários,
        sobrecarregar ou atacar os sistemas, ou enviar conteúdo ofensivo, que viole direitos de
        terceiros ou que não seja de sua autoria quando isso for exigido.
      </p>

      <h2>6. Conteúdo</h2>
      <p>
        As redações que você envia continuam sendo suas. Você nos autoriza a processá-las apenas para
        prestar o serviço. As questões do ENEM são de domínio público do INEP; textos de terceiros
        reproduzidos nelas pertencem aos seus autores e são usados para fins educacionais. [REVISAR
        COM ADVOGADO: direitos autorais dos textos-base das questões.]
      </p>

      <h2>7. Disponibilidade e responsabilidade</h2>
      <p>
        Fazemos o possível para manter a Plataforma no ar, mas ela pode passar por interrupções. Na
        medida permitida em lei, não nos responsabilizamos por decisões tomadas com base nas
        correções ou estatísticas da Plataforma.
      </p>

      <h2>8. Alterações e contato</h2>
      <p>
        Podemos atualizar estes Termos; mudanças relevantes serão comunicadas por e-mail ou na
        Plataforma. Dúvidas: [E-MAIL DE CONTATO]. Foro: [COMARCA].
      </p>
    </>
  );
}
