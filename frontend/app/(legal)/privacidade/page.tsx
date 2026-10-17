import type { Metadata } from "next";

export const metadata: Metadata = { title: "Política de Privacidade" };

export default function PrivacyPage() {
  return (
    <>
      <h1>Política de Privacidade</h1>
      <p>Última atualização: [DATA].</p>
      <p>
        Esta Política explica como [RAZÃO SOCIAL] (&quot;nós&quot;), controladora dos dados, trata os
        dados pessoais na plataforma Rumo1000, de acordo com a Lei Geral de Proteção de Dados (Lei
        nº 13.709/2018, LGPD). Encarregado(a) de dados: [NOME], [E-MAIL DO ENCARREGADO].
      </p>

      <h2>1. Dados que coletamos</h2>
      <ul>
        <li><strong>Cadastro:</strong> nome, e-mail, senha (guardada apenas como hash), data de nascimento e, para menores de 18 anos, o registro do consentimento do responsável;</li>
        <li><strong>Preferências:</strong> fuso horário, ano previsto do ENEM e opção de lembretes;</li>
        <li><strong>Redações:</strong> fotos enviadas, transcrições, textos e resultados das correções;</li>
        <li><strong>Estudo:</strong> respostas às questões, favoritos, sessões de prática e cronogramas;</li>
        <li><strong>Pagamentos:</strong> valor, data, forma de pagamento (PIX ou cartão) e situação das assinaturas e doações. Não recebemos nem guardamos o número do cartão: os dados de pagamento são digitados na página do Mercado Pago;</li>
        <li><strong>Técnicos:</strong> registros de acesso (IP, navegador e horário) para segurança.</li>
      </ul>

      <h2>2. Para que usamos</h2>
      <ul>
        <li>Prestar o serviço: transcrever e corrigir redações, mostrar estatísticas e enviar lembretes (execução de contrato);</li>
        <li>Cobrar a assinatura, registrar doações e cumprir obrigações fiscais (execução de contrato e obrigação legal);</li>
        <li>Enviar e-mails de conta, como verificação e redefinição de senha;</li>
        <li>Segurança e prevenção de abuso (legítimo interesse);</li>
        <li>Medir e melhorar a qualidade da correção usando dados agregados. [REVISAR: base legal]</li>
      </ul>

      <h2>3. Compartilhamento com fornecedores</h2>
      <ul>
        <li>
          <strong>Provedores de inteligência artificial:</strong> o texto e as fotos das redações
          são enviados, para transcrição e correção, a um dos provedores abaixo, conforme a
          configuração da Plataforma: Google (Gemini), Anthropic (Claude) ou OpenAI (GPT). Os três
          processam os dados nos Estados Unidos, o que envolve transferência internacional de
          dados. [REVISAR: termos de retenção e de uso de dados de cada provedor, e a base legal da
          transferência internacional (art. 33 da LGPD). Atenção: no plano gratuito da API do
          Gemini, o Google pode usar o conteúdo enviado para melhorar seus produtos, inclusive com
          revisão humana; no plano pago, não.]
        </li>
        <li>
          <strong>Mercado Pago (pagamentos):</strong> nome e e-mail de quem assina ou doa, e o
          valor da cobrança, para processar o pagamento. Os dados do cartão ou da conta usados no
          pagamento ficam com o Mercado Pago, sob a política de privacidade dele.
        </li>
        <li><strong>Resend (e-mail):</strong> seu e-mail e o conteúdo das mensagens transacionais e dos lembretes.</li>
        <li><strong>Hospedagem:</strong> servidor próprio em [PROVEDOR/LOCALIZAÇÃO DA VPS].</li>
      </ul>
      <p>Dentro da Plataforma, alguns dados ficam visíveis para outras pessoas:</p>
      <ul>
        <li>
          <strong>Professores:</strong> ao fazer uma prova pelo link de um professor, seu nome, seu
          e-mail e suas respostas ficam visíveis para ele. As suas redações não ficam visíveis para
          professores.
        </li>
        <li>
          <strong>Administradores:</strong> veem nome, e-mail, tipo de conta, data de cadastro e os
          pagamentos (valor, data e situação), para controlar o acesso. Não veem suas redações nem
          suas respostas.
        </li>
      </ul>
      <p>Não vendemos seus dados nem os usamos para publicidade.</p>

      <h2>4. Crianças e adolescentes</h2>
      <p>
        Tratamos dados de adolescentes no melhor interesse deles (art. 14 da LGPD). Menores de 18
        anos precisam do consentimento do responsável no cadastro. O responsável pode pedir acesso,
        correção ou exclusão dos dados pelo e-mail [E-MAIL DE CONTATO].
      </p>

      <h2>5. Por quanto tempo guardamos</h2>
      <p>
        Mantemos os dados enquanto sua conta existir. Ao excluir uma redação, apagamos as fotos e o
        resultado. Ao excluir a conta, apagamos todos os seus dados, exceto o que a lei exigir
        guardar (por exemplo, registros de acesso por 6 meses, conforme o Marco Civil da Internet).
        Cópias de segurança são sobrescritas em até [N] dias.
      </p>

      <h2>6. Seus direitos</h2>
      <p>
        Você pode confirmar o tratamento, acessar, corrigir, pedir a portabilidade ou a exclusão dos
        seus dados, revogar consentimentos e obter informações sobre compartilhamento (art. 18 da
        LGPD). A exclusão da conta pode ser feita na página de Perfil; os demais pedidos, pelo e-mail
        [E-MAIL DO ENCARREGADO].
      </p>

      <h2>7. Cookies e segurança</h2>
      <p>
        Usamos apenas um cookie essencial para manter sua sessão (sem cookies de publicidade ou de
        terceiros). As senhas são guardadas com hash forte, o tráfego é criptografado (HTTPS) e os
        arquivos só são acessados por links temporários.
      </p>

      <h2>8. Alterações</h2>
      <p>Avisaremos sobre mudanças relevantes por e-mail ou na Plataforma.</p>
    </>
  );
}
